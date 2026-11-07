# Registered `radio.send_message` — exact-row/material Oracle

Executed source: `ed97452f8` on `codex/oracle-next-20261107`, based on
`origin/main` = `e8187a0c2`.

This is a bounded ORACLE subfamily for one local-preparable registered write. It
does not claim whole-app ORACLE completion, live RPC/HTTP acceptance, provider
breadth, or multi-process concurrency.

## Candidate trace / qualification

The pre-implementation trace is preserved at
`docs/acceptance/evidence/oracle_radio_send_trace_20261107/TRACE.md`.

Reconciliation result:

- the six mini-app host mutations are already covered on main;
- Shopify product is covered on main; blog/article/fulfillment are delivered on
  isolated branches and queued for root review, so they were not re-run;
- `mini_app_run` needs a Firecracker microVM/rootfs and is **unqualified** for
  this local lane;
- `brennan.books.*`, `brennan.outlook.create_draft` already have producer
  by-id/material readback;
- remaining lazy local mutations: `radio.create_thread`, `radio.send_message`,
  `workspace.commit`, `workspace.note`.

Selected: `radio.send_message` — enabled by default, durable
`LateralMessage.id`, existing `radio.read_inbox`/`get_thread_snapshot` read
primitive, and a real Generic claim/replay path. It needs no provider account,
credential, live authority, VM, or HTTP leaf. No HTTP is doubled because this
candidate has no provider HTTP; the real scratch SQLite store is used.

## Contract / consumers

- Registry/action: `core/agent_radio/radio_actions.py::radio_send_message`
  (`effects=[{"effect":"send","scope":"local"}]`).
- Service: `core/agent_radio/radio_service.py::send_message` enforces
  mention-first, thread membership, open thread and budget, then commits the
  row.
- Read primitive: `radio.read_inbox` / `get_thread_snapshot`; the verifier
  re-reads the exact `LateralMessage.id` row and its `AgentThread` in a fresh
  session.
- Consumer: real `GenericAgent._step_act_unaudited` durable claim + shared
  Oracle; durable receipt projector/matcher in `core.oracle`.
- Protocol: `docs/architecture/AGENT_RADIO.md` §Protocol — mention-first,
  thread-scoped, no broadcast; `agent_threads` + `lateral_messages` rows.

## Failure first

The predecessor handler committed the message and returned raw success without
re-reading the exact row or comparing the authorized material. Against the
`HEAD^` implementation the new controls are **20 failed, 1 passed, exit 1**
(`failure-first.log`). The one pass is the already-honest lost-confirmation
control.

## Implementation

- `core/agent_radio/radio_mutations.py`:
  - canonical authorized material: thread id, server-owned sender agent id,
    content, normalized mention set, target, `requires_response`, tenant;
  - producer re-reads the exact message id + thread from a fresh session;
  - pre-effect policy/access/budget/disabled/tier refusals are explicit
    `failed_before_effect`;
  - a post-commit generic exception is `uncertain`, never fabricated failure or
    success;
  - relay wakeup failure cannot turn a committed row into failure;
  - durable receipt projector/matcher stores the authorized material.
- `radio_actions.py` keeps the legacy `success`/`message_id`/`thread_id`/
  `mentions` shape while adding the proof envelope.
- `request_expectations.py` freezes the canonical radio payload digest.
- `postcondition_verifiers.py` re-reads the exact message/thread in a fresh
  session and compares target, sender, content, mentions, response flag and
  tenant scope.

No global provider eligibility, permission, consent, feedback/CAS or authority
policy changed. Single-tenant compatibility is retained: an empty thread tenant
is accepted; two conflicting non-null tenants are unverified.

## Controls

`backend/tests/test_oracle_radio_send.py` covers exact send, target/response
material, pre-effect refusals, same-operation replay and restart without a
second row, changed current content/mentions/target/response flag/tenant scope,
missing row, wrong id, absent/unavailable readback, unidentifiable effect, lost
confirmation, changed same-operation material, and failed identity receipt.
Existing fake-DB radio controls were updated only to expose the appended row to
the required by-id readback.

## Exact runs

`run_and_capture.py` is the executable spec: existing Python 3.14.7,
`TESTING=1`, synthetic `SECRET_KEY`, fresh scratch SQLite/data/Lance/output,
`ATOM_RADIO_ENABLED=true`, blank provider credentials.

- `failure-first.log` / `failure-first-exit.json`: predecessor, **exit 1**,
  20 failed / 1 passed.
- `focused.log` / `focused-exit.json` / `focused.xml`: current implementation
  across new radio Oracle + existing radio service/action/tool + registry/
  Generic/connected/effect-family suites, **367 passed, exit 0**.

No live model/provider/server/browser/account/credential/install/spend/send/
deployment/dev-database action was made. The scratch SQLite database was pruned
after log/XML capture; `run_and_capture.py` recreates it.

## Ownership and remaining limits

- Agent1 owns image-content receipt on a separate worktree; no image/product
  files were touched here.
- This worker owns the radio send producer/verifier/evidence.
- Root owns maturity, independent acceptance and final verification.

Remaining qualification limits: `radio.create_thread` remains an uncovered
alternate in the same family; `workspace.commit`/`workspace.note` remain
deferred local rows; `mini_app_run` remains unqualified without the guest
runtime; no live RPC/HTTP server, multi-process/PostgreSQL concurrency, or
provider breadth is claimed. The originally delivered Shopify blog/article/
fulfillment branches and root Decimal formatter fixes are not modified by this
packet.
