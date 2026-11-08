# `radio.create_thread` — normal MCP replay-class repair

Executed source: `9c5219242` (repair commit on
`codex/oracle-refresh-20261107`, parent `5d7ca586f` root MCP test, merged main
`cf5e98191`). Root's atomic first-DML repair at `7e91a3c91` remains preserved and
qualified; this packet addresses the normal `MCPService.call_tool ->
action_registry -> producer` replay class that has no Generic claim wrapper.

## Root finding

Root's frozen-`f010` probe recorded **4 failed, 3 passed, actual exit 1**:

- same operation/material, two MCP calls -> two threads;
- same operation/changed name -> a second thread;
- missing operation id -> committed thread with no durable operation identity;
- accepted row + readback timeout, retry same operation -> another thread.

Root originals are preserved byte-for-byte under `root-originals/`:
`root-radio-mcp-replay-negative.log`, `.exit.json`, and
`root-radio-mcp-replay-negative-binding.json`. The binding explicitly notes the
runner template flag `diagnostic_uncommitted_candidate=true` is metadata; the
listed loaded bytes match the frozen Git commit, and no runtime/test diff was
found.

## Repair

The shared producer/persistence boundary now resolves replay after the existing
first-DML authority claim and before any `INSERT agent_threads`:

1. Read the raw creator/member authority snapshot; the first writer DML is still
   the deterministic conditional `UPDATE agent_registry` claim.
2. After the claim, resolve exact `creator + operation_id` rows from
   `AgentThread.metadata_json` (exact string identity, no prefix/normalization).
3. One row with matching frozen name/normalized roster/scope/tenant is the
   original effect: return the original thread id with `replayed/already_applied`
   markers and a fresh read receipt, no second insert.
4. Changed material on the same exact key returns typed
   `proven_not_applied`/`operation_conflict`, keeps the original row, and writes
   nothing.
5. Multiple historical rows for the exact key fail closed with
   `proven_not_applied`, zero new write, and all historical rows retained; no
   first/latest selection or merge.
6. Authority loss before the claim refuses before effect and reports the known
   original identity as `committed_unverified`; it never certifies replay
   success.
7. Readback uncertainty retains the known thread/op id. A same-op retry
   reconciles the original row instead of resending.
8. Missing trusted context operation identity mints a server-owned exact id,
   persists it in thread metadata, and echoes it (`operation_source=
   server_generated`). Caller business args never override the trusted context
   id. Distinct explicit operations remain distinct intents.

The authority CAS still serializes creators: concurrent same-key calls create
one winner in the actual SQLite interleaving. This packet makes no PostgreSQL,
multi-worker or soak claim.

## Caller-path trace

| caller | path | result |
|---|---|---|
| Generic | `GenericAgent._step_act_unaudited` -> MCP -> registry -> producer | existing claim + producer replay; cross-caller tests pass |
| Assignment | `AssignmentExecutor._action_registry_adapter` -> registry -> producer | operation id from step/context; same-op replay test passes |
| MCP | `MCPService.call_tool` -> registry -> producer | root 4 MCP cases pass; replay matrix passes |
| Registry/RPC | `action_registry` / `POST /api/rpc/{action}` | producer replay applies when an agent context is present; the generic RPC context still lacks `agent_id`, so radio writes refuse pre-effect there |
| Service | `radio_service.create_thread` direct callers | unchanged; no producer replay/CAS layer |
| Fleet adapter | `radio_adapter.attach_thread_for_chain` -> service -> direct insert | retained parallel trusted writer; existing adapter tests pass, but this packet does NOT qualify the fleet adapter for the MCP replay contract and does not force it through the new policy |

Shared helper change: `radio_thread_mutations` imports the accepted
`core.agent_radio.radio_mutations.read_thread` helper now on main instead of
copying it. Main send-message and fulfillment verifiers/helpers are preserved;
no provider tree was touched.

## Controls at `9c5219242`

All pytest used the shared bounded gate, fresh unique DB/data/Lance/output/
basetemp and synthetic `SECRET_KEY`.

| log | result |
|---|---|
| `focused.log` (create Oracle + root authority 3 + root MCP 4 + replay matrix) | **47 passed**, exit 0 |
| `root-frozen-first-dml.log` | **3 passed**, exit 0 |
| `merged-send-registry-request.log` | **85 passed**, exit 0 |
| `radio-units.log` | **45 passed**, exit 0 |
| `heavy-full-radio.log` (`test_covpush_w80a_radio.py`, heavy 4 GiB floor) | **219 passed**, exit 0 |

New replay controls include: missing/overridden identity, distinct operations,
Generic<->MCP cross-caller replay, assignment-adapter replay, authority loss,
ambiguous duplicate rows, readback row-absent recovery, concurrent same material
(one thread), and concurrent changed material (one winner). The original
Generic exact-row/replay/identity-poison/no-suitable/stale-authority/rollback
tests remain.

## Registry state

`registry-counts.json` records the current source counts:
**98 actions / 30 declared mutations / 27 covered / 3 uncovered**
(`mini_app_run`, `workspace.commit`, `workspace.note`). Counts are unchanged
from the `7e91a3c91` map; the older `908026a39` 25/5 map remains its dated
historical capture and was not rewritten. Static counts are not runtime
qualification; whole-app ORACLE remains open.

## Boundaries

No live provider/model/account/credential/send/spend/install/deploy/VM/
PostgreSQL/sandbox. No new table, migration, operation ledger, engine, router,
approval lifecycle, role gate or fleet-adapter policy. Root owns independent
review, PR, CI and merge.
