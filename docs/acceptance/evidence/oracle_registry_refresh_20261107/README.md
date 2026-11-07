# Enabled registry → verifier refresh — 2026-11-07

Executed source: `36fa4ce39dd19a6b53b662699e5ceebede129df1` (`origin/main`).
The inventory runner imports the two lazy registration modules exactly as the
RPC router and MCP service do:

- `core.agent_radio.radio_actions`
- `core.bpe.actions`

This is a source-bound discovery matrix, **not** runtime coverage and not
whole-app acceptance. The historical `oracle_registry_coverage_20261107*`
packets (90 actions / 26 mutations / 15 covered) are preserved but stale.

## Authoritative counts at this source

| bucket | count |
|---|---|
| registered actions | **98** |
| declared mutations | **30** |
| — local durable | 20 |
| — external/provider | 10 |
| mutations with an independent verifier | **24** |
| mutations without a verifier | **6** |
| explicit read-only | 67 |
| plan-output validators | 1 (`goals.decompose`, structural) |
| undeclared | 0 |

## The six uncovered mutations, with status

| action | scope | status | why |
|---|---|---|---|
| `radio.create_thread` | local | **selected for the next finite trace** | durable `AgentThread` row, exact by-id read primitive, real roster/tenant authority material, no verifier |
| `radio.send_message` | local | **implemented, pending merge** | exact-row/material producer + verifier + replay work exists on `codex/oracle-next-20261107` (`3a188840d`, PR chain); deliberately not duplicated here |
| `workspace.commit` | local | **deferred** | BPE Progress is in-process state rendered into the execution record; no exact per-effect id comparable to a durable row |
| `workspace.note` | local | **deferred** | notes are a pre-consolidation buffer; durability is episode-close/consolidation, not the action call |
| `mini_app_run` | local | **unqualified for this lane** | requires Firecracker microVM/rootfs; no local fixture is permitted |
| `shopify_create_fulfillment` | external | **pending owner review** | provider write under root worker `56636` (PRs 745/748/749/750); this worker did not touch those trees |

No declared mutation is classified disabled. AgentRadio and the BPE workspace
default ON; disabled/deferred rows above are explicit qualification states, not
inferred from a static count.

## Provider reconciliation at `36fa4ce39`

`origin/main` already carries independent verifiers for:

- `shopify_create_product`
- `shopify_create_blog`
- `shopify_create_article`

`shopify_create_fulfillment` remains uncovered and is owned by the active
provider-integration worker; it is excluded from this worker's scope. The
earlier snapshots' "Shopify blog/article uncovered" lines were correct for
their older source and are not current.

## Machine-readable map

`inventory.json` records every action, effects, verifier state and bucket.
`generate_inventory.py` reproduces it. `inventory-run.log` and
`inventory-exit.json` record the actual run (`exit 0`).

## Boundaries

- No all-827 sweep and no broad campaign.
- No live provider, model, account, credential, send, spend, install, deploy,
  VM, PostgreSQL, or sandbox execution.
- Static counts are discovery evidence only; they never establish runtime
  coverage.
- Root retains independent acceptance and merge.
