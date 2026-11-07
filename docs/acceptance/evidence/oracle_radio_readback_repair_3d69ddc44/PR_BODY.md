# Preserve known radio message identity across readback failure

## Summary

Root's permanent control `9aba74234`
(`backend/tests/test_lead_radio_readback_identity.py`) found that
`radio_mutations.send_message` discarded a known committed `LateralMessage.id`
when the independent readback raised `TimeoutError`. The producer had one try
around dispatch plus readback, so a read failure was reported as a generic send
failure with `remote_id=''`.

This checkpoint separates pre-effect failures from post-commit readback
failures, preserves the known message id in the uncertain receipt, and keeps the
existing no-resend/replay semantics. Dispatch, Generic claims, shared Oracle,
and the real SQLite service are otherwise unchanged.

## Changes

- `core/agent_radio/radio_mutations.py`
  - dispatch and readback are separate phases;
  - policy/access/budget/RadioError before dispatch remain
    `failed_before_effect`;
  - any post-commit readback exception (including `RadioError`) is
    `uncertain` with the known `remote_id` and
    `provider_receipt.remote_id`;
  - no second send on replay.
- `tests/test_oracle_radio_send.py`
  - known-id TimeoutError, RuntimeError and RadioError readback controls;
  - replay-after-readback-failure no-resend control;
  - valid exact twin retained.

## Verification

- Root supplied control: passes.
- Failure-first against pre-repair `9aba74234`: 5 failed, exit 1.
- Focused merged-source controls: 374 passed, exit 0, including root control,
  radio Oracle/service/action/tool, registry/Generic/Oracle families, and the
  merged wait-neutral tests.

## Boundaries

- No live server/model/provider/account/credential/send/spend/install.
- Tenant mismatch is post-effect receipt verification only; it is not a
  pre-effect authorization gate. The current single-tenant contract remains
  open-thread plus thread membership, with nullable thread tenant.
- Shared fixes from `origin/main` are merged at `3d69ddc44`, not removed.
- Root owns independent review/acceptance.
