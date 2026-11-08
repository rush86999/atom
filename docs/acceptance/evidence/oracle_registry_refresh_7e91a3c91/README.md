# Enabled registry → verifier refresh — final repair source

Executed source: `7e91a3c91` (authority-linearization repair on top of the
normal merge `7a587f646` of current main `cf5e98191`). This is a **new-source**
map; the earlier `oracle_registry_refresh_20261107/` packet remains its dated
historical capture and its counts were not rewritten.

The inventory runner imports the lazy AgentRadio and BPE modules exactly as the
RPC router and MCP service do.

## Authoritative counts at this source

| bucket | count |
|---|---|
| registered actions | **98** |
| declared mutations | **30** |
| — local durable | 20 |
| — external/provider | 10 |
| mutations with an independent verifier | **27** |
| mutations without a verifier | **3** |
| explicit read-only | 67 |
| plan-output validators | 1 (`goals.decompose`, structural) |
| undeclared | 0 |

## Remaining uncovered mutations

| action | scope | status |
|---|---|---|
| `workspace.commit` | local | deferred — in-process BPE Progress rendered into the execution record; no exact per-effect durable id comparable to a thread/message row |
| `workspace.note` | local | deferred — pre-consolidation buffer; durability is episode-close/consolidation, not the action call |
| `mini_app_run` | local | unqualified for this lane — requires Firecracker microVM/rootfs |

`radio.create_thread` is covered at this source by the first-DML authority CAS
and exact-row verifier. `radio.send_message` is covered by current main's
accepted general helpers (reused, not duplicated). `shopify_create_fulfillment`
is covered by current main and its provider work; no provider tree was touched
here.

No declared mutation is disabled. AgentRadio and BPE default ON.

## Machine-readable map

`inventory.json` records every action, effects, verifier state and bucket.
`generate_inventory.py` reproduces it. `inventory-run.log` and
`inventory-exit.json` record the actual run (`exit 0`).

## Boundaries

- Static counts are discovery evidence, never runtime coverage or acceptance.
- No all-827 sweep.
- No live provider/model/account/credential/send/spend/install/deploy/VM/
  PostgreSQL/sandbox execution.
- Root owns independent review, PR, CI and merge.
