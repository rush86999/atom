# Normal registered-request expectations — Agent 1 evidence (2026-11-07)

Source: branch `codex/generic-request-context-20261107`, starting from the
joint host/caller candidate `fbe7a5975`. This evidence covers the commits that
add the shared request-expectation builder, its controls and the
result-envelope namespace scrub.

## Root negative reproduced

The supplied probe `/private/tmp/test_lead_generic_mini_request_binding.py`
was run once against `fbe7a5975` with a fresh scratch SQLite DB and project
Python 3.14: **1 FAIL (Generic) / 1 PASS (Assignment)**. The Generic failure
was exactly the reported consumer gap: the real scaffold producer created one
app + one audit row, but the observation was `success=false`,
`status=uncertain`, `oracle_verified=false`,
`oracle_evidence="no frozen operation/request binding"`,
`requires_reconciliation=true`, `retryable=false`.

The probe was then run against the fixed head: **2 passed**. The copy used for
the final run differs from the supplied probe only in its scratch output path
(so the root's historical captures are not overwritten); its test body and
assertions are byte-identical.

## Fix under test

`backend/core/oracle/request_expectations.py` is the single builder used by
both the Normal Generic consumer and `AssignmentExecutor._action_registry_adapter`.
It freezes the operation id, request digest, tenant/workspace/actor scope,
presentation material and action-specific proof fields from the accepted
business args plus server-owned runtime identity. `_oracle_expected_*` is a
protected namespace: model/body args and handler result envelopes are stripped
and cannot populate it.

Uncertain durable claims now reconcile from a fresh independent readback of
the frozen request. A confirmed postcondition moves the original claim to
succeeded without a second dispatch; absent proof remains honestly uncertain.

## Run scope

- Project Python 3.14 (`backend/venv314`).
- `TESTING=1`, explicit fresh scratch SQLite database and `--basetemp` under
  the approved temp root.
- Scratch `host` fixture for the mini-app family; real registered handlers and
  independent DB readback.
- Governance is explicitly bypassed (`pre_approved=True`) in the controlled
  consumer probes. No model, provider, guest microVM, credentials, spend,
  send or deployment is used.

See `final-gate.log` for the exact command/exit and `MANIFEST.json` for the
source identities. The pre-existing unrelated failure in
`tests/test_covpush_w36_oracle_vfs.py::TestTaskVerifier::test_task_exists`
(stale `SimpleNamespace(id=...)` fixture without `title`/`board_id`) is not
caused by this change and is recorded separately in `known-preexisting-failure.log`.
