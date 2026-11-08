# `radio.create_thread` — normal-MCP replay repair (current-main successor)

Executed source: `90eac34a7` — normal merge of current main `8ded00232` into the
MCP replay repair. Parent repair: `9c5219242`; root MCP test: `5d7ca586f`; the
atomic first-DML repair `7e91a3c91` remains preserved and qualified.

## Root finding

Root's frozen-`f010` MCP probe was **4 failed, 3 passed, actual exit 1**:
same-op/material created two threads; same-op changed name created a second;
missing op id committed without durable identity; readback timeout retry
resent. `MCPService.call_tool -> action_registry` has no Generic claim wrapper.

Root originals are preserved byte-for-byte under `root-originals/`:
`root-radio-mcp-replay-negative.log`, `.exit.json`,
`root-radio-mcp-replay-negative-binding.json`. The binding records that the
runner's `diagnostic_uncommitted_candidate=true` is template metadata, the
listed loaded bytes match the frozen Git commit, and no runtime/test diff was
found.

## Repair (unchanged by the goals-main merge)

After the existing first-DML authority CAS and before `INSERT agent_threads`,
the producer resolves exact `creator + operation_id` rows from thread metadata:

- one matching row -> replay original id/material/read receipt, no second
  insert;
- changed material -> typed `proven_not_applied`/`operation_conflict`, original
  retained, no new write;
- multiple historical rows for the exact key -> fail closed, zero new write,
  rows retained, no first/latest selection;
- authority loss -> pre-effect refusal with the known original identity marked
  `committed_unverified`; never verified replay success;
- readback uncertainty -> known thread/op id retained; same-op retry reconciles
  the original row without resend;
- missing trusted context operation identity -> server-owned exact id minted,
  persisted in metadata, echoed; caller args cannot override context identity;
- distinct explicit operations remain distinct intents;
- concurrent same-key writers use the existing authority CAS/SQLite lock and
  create one winner in the actual SQLite interleaving (no PG/multiworker/soak
  claim).

`radio-source-identity.json` proves the radio/helper/test bytes are identical
between `9c5219242` and `90eac34a7` (the merge changed goals/frontend only).

## Caller-path trace

| caller | result |
|---|---|
| Generic | existing claim + producer replay; tested |
| Assignment | operation id from step/context; same-op replay tested |
| MCP | root 4 cases + replay matrix tested |
| Registry/RPC | MCP/action-registry path tested; generic RPC still lacks `agent_id`, so radio writes refuse pre-effect |
| Service | `radio_service.create_thread` unchanged; direct callers have no producer replay/CAS |
| Fleet adapter | `radio_adapter.attach_thread_for_chain` remains a parallel trusted writer; existing adapter tests pass, but this packet does NOT qualify it for the MCP replay contract and does not force it through the new policy |

Shared helper change: `radio_thread_mutations` imports main's accepted
`radio_mutations.read_thread` rather than copying it. Main send-message and
fulfillment helpers/verifiers are preserved.

## Controls

| log | result |
|---|---|
| `focused.log` | **47 passed**, exit 0 |
| `root-frozen-first-dml.log` | **3 passed**, exit 0 |
| `merged-send-registry-request.log` | **85 passed**, exit 0 |
| `radio-units.log` | **45 passed**, exit 0 |
| `heavy-full-radio.log` at `90eac34a7` | **exit 75, not dispatched** at 3.85 GB < 4 GiB heavy floor |
| parent `9c5219242` heavy log (in `../oracle_radio_mcp_replay_9c5219242/`) | **219 passed**, exit 0 |

The 219-case suite was run whole at the parent and attempted whole at this
merge source; it was not split or dropped. The only difference between the two
sources is non-radio goals/frontend code (`radio-source-identity.json`).

Focused controls cover missing/overridden identity, distinct operations,
Generic<->MCP cross-caller replay, assignment-adapter replay, authority loss,
ambiguous duplicate rows, readback row-absent recovery, concurrent same material
and concurrent changed material. Original Generic exact-row/replay/
identity-poison/no-suitable/stale-authority/rollback controls remain.

## Registry state

`registry-counts.json`: **98 actions / 30 declared mutations / 27 covered /
3 uncovered** (`mini_app_run`, `workspace.commit`, `workspace.note`), unchanged
from `7e91a3c91`/`9c5219242`. The older `908026a39` map remains its dated
historical capture. Static counts are not runtime qualification; whole-app
ORACLE remains open.

## Boundaries

No live provider/model/account/credential/send/spend/install/deploy/VM/
PostgreSQL/multiworker/soak. No new table, migration, operation ledger, engine,
router, approval lifecycle, role gate or fleet-adapter policy. Root owns
independent review, PR, CI and merge.
