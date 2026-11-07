# Radio readback identity repair — exact-source evidence

Executed source: `3d69ddc44` (merge of the radio repair with current
`origin/main`). Narrow fix commit: `55224dfb9`.
Root permanent negative control: `9aba74234`
(`backend/tests/test_lead_radio_readback_identity.py`).

Root's supplied negative log/exit is preserved at:

- `/private/tmp/root-radio-known-id-negative.log`
- `/private/tmp/root-radio-known-id-negative-exit.json`

Byte copies are retained in this packet as `root-negative.log` and
`root-negative-exit.json`.

No prior source/negative packet was modified.

## Defect

The producer combined dispatch and independent readback in one try. A
`TimeoutError` from `read_message` therefore fell into the generic
send-failure branch and returned `remote_id=""`, discarding the known
`LateralMessage.id` even though the row had committed. Root's permanent control
failed with `assert '' == '<actual row id>'`.

## Narrow repair

- Dispatch and readback are separate phases.
- Pre-effect `RadioPolicyError` / `RadioAccessError` / `RadioBudgetExceeded` /
  `RadioError` from the send remain explicit proven-no-effect refusals.
- Any exception from the post-commit read primitive — including a `RadioError`
  raised by readback — is an uncertain readback failure, never a safe
  pre-effect refusal.
- The known message id is preserved in top-level `remote_id` and
  `provider_receipt.remote_id`.
- No-repeat semantics are unchanged: the claim stays uncertain and a replay
  does not create a second row.
- A known-id timeout, generic readback error, and readback `RadioError` are
  covered; the exact valid twin and replay no-resend remain covered.

No Generic claim/shared Oracle/real SQLite service design changed.

## Tenant boundary (honest assessment)

The current single-tenant radio contract in
`radio_service.send_message` is: thread exists, thread is open, and the sender
is a thread member (`is_member`). `AgentThread.tenant_id` is nullable and is
**not** a pre-effect send-authorization gate.

The Oracle records the thread tenant and marks a conflicting non-null tenant as
unverified on replay/readback. That is a post-effect receipt mismatch only. It
does **not** qualify tenant authorization and does not prevent the send. This
repair does not broaden or tighten provider/tenant authority.

## Merge reconciliation

`origin/main` had advanced to `e39e2af2f` (wait/maturity fixes). The branch was
merged normally, producing `3d69ddc44`; shared fixes and their tests were kept.
Affected controls were rerun on the merged tree.

## Evidence runs

`run_and_capture.py` uses the existing Python 3.14.7 interpreter, `TESTING=1`,
synthetic `SECRET_KEY`, fresh scratch SQLite/data/Lance/output,
`ATOM_RADIO_ENABLED=true`, and blank provider credentials.

- `failure-first.log` / `failure-first-exit.json`: pre-repair
  `radio_mutations.py` from `9aba74234`; root control + known-id/replay
  controls **5 failed, exit 1**.
- `focused.log` / `focused-exit.json` / `focused.xml`: merged source across
  root control, full radio Oracle suite, existing radio service/action/tool,
  registry/Generic/connected/effect-family and merged wait-neutral controls:
  **374 passed, exit 0**.

No live server/model/provider/account/credential/send/spend/install was used.
The scratch SQLite database was pruned after log/XML capture; the runner
recreates it. Root owns independent review and acceptance.
