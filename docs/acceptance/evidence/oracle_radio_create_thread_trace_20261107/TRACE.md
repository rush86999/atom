# ORACLE candidate trace — `radio.create_thread`

Executed source for the probe: `36fa4ce39dd19a6b53b662699e5ceebede129df1`.
This is a finite trace for one enabled local durable write. It does not claim
whole-app ORACLE completion.

## Reconciliation

The refreshed map (`../oracle_registry_refresh_20261107/`) leaves six declared
mutations without a verifier. They are not interchangeable:

| candidate | decision |
|---|---|
| `radio.create_thread` | **selected** — durable `AgentThread` row; exact `get_thread`/`get_thread_snapshot` read primitive; real roster/creator/tenant material; enabled by default |
| `radio.send_message` | exact-row/material producer, verifier and replay controls already exist on `codex/oracle-next-20261107` (`3a188840d`); never duplicated here |
| `workspace.commit` / `workspace.note` | deferred — BPE state is in-process and rendered into the execution record; no exact per-effect id comparable to a durable row |
| `mini_app_run` | unqualified — needs Firecracker microVM/rootfs |
| `shopify_create_fulfillment` | provider write owned by root worker `56636` (PRs 745/748/749/750); not touched |

The earlier `radio.send_message` trace already named `radio.create_thread` as
the alternate. With send complete on its branch, create-thread is the next
enabled local durable row.

## Contract trace

- Registry action: `core/agent_radio/radio_actions.py::radio_create_thread`
  (`effects=[{"effect": "create", "scope": "local"}]`).
- Service: `core/agent_radio/radio_service.py::create_thread` de-duplicates the
  roster, inserts the creator, writes one `AgentThread` row and commits it.
- Durable model: `core/models.py::AgentThread` (`agent_threads`), with `name`,
  `created_by_agent_id`, `member_agent_ids`, `tenant_id`, `metadata_json` and
  `status='open'`.
- Exact read primitive: `radio_service.get_thread(db, thread_id)` and
  `get_thread_snapshot(db, thread_id, agent_id)`; the row is addressable by
  `AgentThread.id`.
- Consumer: real `GenericAgent._step_act_unaudited` durable claim + shared
  Oracle; the same verifier registry used by the assignment adapter.
- Protocol: `docs/architecture/AGENT_RADIO.md` §Protocol.

Authorized material to freeze and compare: exact thread name, server-owned
creator `agent_id`, normalized roster (creator + de-duplicated members),
`scope_hint`/metadata scope, and tenant. The thread id locates the row; it is
not material.

## Failure-first evidence (current source)

Command: the shared bounded gate around the probe in this directory; actual
test exit **1** (gate dispatched, 5.12 GB free before, above the 4 GiB floor).

The probe drives the real registry action, real `radio_service` persistence and
real `GenericAgent` mutation consumer against scratch SQLite. It shows:

1. the thread **is** persisted with the exact name, creator, roster, scope and
   tenant; and
2. the consumer cannot certify it — `oracle_verified=False` with evidence
   `no registered postcondition verifier`, so the result is downgraded to
   `action_result='uncertain'`; and
3. a roster naming an agent from a **different tenant** is persisted, and the
   consumer has no verifier that evaluates the tenant/member contradiction.

`probe.log` and `probe-exit.json` preserve the raw run. `gate-state.json` is
the wrapper's own record: its `status` field follows the wrapper's
`SystemExit` path, while `actual_exit` is the child test exit **1**, confirmed
by `probe.log` (`2 failed`). This is the gap to close; it is not a claim that
the row was lost.

## Authority boundary (honest assessment)

The current single-tenant radio contract validates only that the name and
member list are non-empty. `create_thread` does **not** re-read the creator or
members from `AgentRegistry`, and it accepts `tenant_id` from the dispatch
context without checking that the creator belongs to it. A thread may therefore
claim a nonexistent or cross-tenant member. This trace does not broaden or
tighten the existing send-message authority contract; it records the gap for
the next finite implementation.

## Next-row plan (existing general mechanisms only)

1. Producer: keep the legacy success shape, add a proof envelope; re-read the
   exact `AgentThread.id` in a fresh session after commit; bind the
   server-owned operation id in thread metadata so an uncertain replay can
   locate the same row.
2. `core/oracle/request_expectations.py`: freeze the name, creator, normalized
   roster, scope and tenant, and derive the payload digest from those fields.
3. `core/oracle/postcondition_verifiers.py`: register a fresh-session verifier
   that compares the exact row and, where authoritative `AgentRegistry` rows
   exist, requires creator/member tenant consistency; a contradiction is
   unverified, never a copied-details success.
4. Durable receipt projector/matcher for create-thread so a succeeded claim
   replays the exact row and no second thread is created.
5. Controls: valid twin, changed name/roster/creator/tenant negatives, missing
   row/wrong id, cross-tenant and nonexistent-member authority negatives,
   pre-effect refusals, and same-operation replay without a duplicate.
6. Add the focused files to the existing ORACLE CI gate; root owns CI and
   acceptance.

## Ownership and boundaries

| owner | scope |
|---|---|
| this worker | evidence, trace and probe in these two directories |
| root worker `56636` | provider integration PRs 745/748/749/750 — not touched |
| root | maturity, independent acceptance, merge and CI |

No production file was changed. No new engine, router, store or receipt
mechanism was introduced. No live provider, model, account, credential, send,
spend, install, deploy, KVM, PostgreSQL or sandbox execution was used. The App
single-tenant contract is unchanged.

## Environmental note

An earlier supervisor process (`73593`) exited 1 with `ENOSPC` while saving
state; root confirmed no surviving process and retained this worktree at
`36fa4ce39` plus the refresh inventory. The inventory and probe above were
rerun cleanly after that interruption. The interruption is not treated as a
test verdict.
