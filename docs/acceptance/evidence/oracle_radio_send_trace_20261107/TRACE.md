# ORACLE candidate trace — `radio.send_message`

Base: `origin/main` = `e8187a0c2`.
This phase publishes the candidate trace/ownership only; implementation follows
in a separate commit.

## Reconciliation

Current main's generated coverage rows are stale for the six mini-app host
mutations (they are covered in `core/oracle/postcondition_verifiers.py` on
main). Re-importing the real registry with the lazy AgentRadio/BPE modules
loaded yields these declared mutations still without a postcondition verifier:

| candidate | source / consumer | existing read primitive | qualification |
|---|---|---|---|
| `radio.send_message` | `core/agent_radio/radio_actions.py` → `radio_service.send_message` → `lateral_messages` row | `radio_service.get_thread_snapshot` / `radio.read_inbox`; exact `LateralMessage.id` row | **selected**: enabled by default, local-preparable, durable message id + material, real Generic claim/replay |
| `radio.create_thread` | same family | thread row / snapshot | alternate; chosen send because it has a durable material effect |
| `workspace.commit` / `workspace.note` | lazy BPE actions | `workspace.track` / recall | deferred: no exact per-effect id/receipt comparable to a message row |
| `mini_app_run` | `mini_app_tool` | CanvasState after guest run | **unqualified**: needs Firecracker microVM/rootfs; no local fixture |
| `shopify_create_blog/article/fulfillment` | Shopify registry | provider by-id | already delivered on isolated branches / under root review; product is on main. Not re-run here |
| `brennan.books.*`, `brennan.outlook.create_draft`, `mini_app_scaffold/write_logic/publish/install/revert/db_write` | connected/mini-app | existing exact readback | already covered on main; not candidates |

The selected row is the next genuinely enabled registered mutation whose
producer returns a raw success and whose exact target/material is not re-read.
It is local durable state, so there is no provider HTTP leaf to double: the
scratch SQLite DB and the real service/model code are used unmodified. The
action is reachable through the existing `POST /api/rpc/radio.send_message`
route, but the controlled fixture drives the real registry/Generic consumer
directly; no live server/browser is used.

## Source / consumer / contract trace

- Registry: `core/agent_radio/radio_actions.py::radio_send_message`
  (`effects=[{"effect":"send","scope":"local"}]`).
- Service: `core/agent_radio/radio_service.py::send_message` enforces
  mention-first, thread membership, open thread and budget; commits the
  `LateralMessage` row.
- Read primitive: `radio_service.get_thread_snapshot` exposes message
  `id/from_agent_id/to_agent_id/content/mentions/created_at`; the exact row is
  also addressable by `LateralMessage.id` in a fresh session. Existing
  `radio.read_inbox` is the agent-facing read action.
- Generic consumer: `GenericAgent._step_act_unaudited` claims the operation in
  `task_operation_records`, freezes request expectations, invokes the registry
  action, and stamps the Oracle verdict. Same-operation replay must re-read the
  exact message, never resend.
- Existing receipt/claim mechanisms: `core.oracle` durable receipt
  projector/matcher registries, `build_durable_effect_result`, and
  `durable_result_conflicts`. No new receipt store, router or operation engine.
- Internal contract: `docs/architecture/AGENT_RADIO.md` §Protocol
  (`radio.send_message(thread_id, content, mention_agent_ids, requires_response,
  metadata)`), §Design decision 2 (mention-first, thread-scoped, no broadcast),
  and the `agent_threads`/`lateral_messages` persistence contract.
- Authorized material to verify: exact thread id, server-owned sender agent id,
  exact content, normalized mention set, `to_agent_id`, `requires_response`,
  and thread tenant scope. The message id locates the row; it is not material.

## Ownership row

| owner | scope | files |
|---|---|---|
| this worker | `radio.send_message` producer-by-id/material verification, claim replay/no-resend, Oracle/evidence | `core/agent_radio/radio_mutations.py` (new), `radio_actions.py`, `oracle/postcondition_verifiers.py`, `oracle/request_expectations.py`, new radio Oracle tests/evidence |
| Agent1 | image-content receipt, separate worktree | image/Shopify product image files only |
| root | maturity, independent acceptance, final verification | review/integration only |

No global provider eligibility, permission, consent, feedback/CAS or authority
policy will be changed. Single-tenant compatibility is retained (thread
`tenant_id` may be null; a conflicting non-null tenant is unverified, not
silently accepted).
