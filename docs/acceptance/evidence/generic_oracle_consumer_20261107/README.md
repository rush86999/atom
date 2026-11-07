# GenericAgent outcome/retry consumer — evidence

Source base: `8bbad92cbef69a5e540afd30d0e748139590030f`
(fail-first reviewed matrix checkpoint on
`codex/generic-oracle-consumer-20261107`).
Code/test commit: `ec9dede00` on the same branch.

## Defect reproduced at the checkpoint

`LEAD_GENERIC_PROBE.py` at the base produced 2 failures / 1 pass through the
real `GenericAgent._step_act_unaudited` consumer:

1. A declared `create` committed a real scratch-SQLite row and returned its own
   `success/applied` envelope; with no registered verifier the observation
   still read as business success.
2. The same landed write followed by `TimeoutError` returned "You may try once
   more if critical" without an independent verdict — a retry could duplicate
   the effect.
3. The explicit-read twin passed.

The reviewed matrix added missing/None/raising/refuting verdict controls, a
positive independent readback, disabled-oracle controls, plan-output and read
twins, and frozen-request/operation-forgery twins. Baseline: 10 failed, 4
passed.

## Repair (existing shared mechanisms, no new table/lifecycle)

- `GenericAgent._step_act_unaudited` freezes the authorized request before
  governance/handler. The handler receives a deep copy; only the pre-dispatch
  snapshot may supply `_oracle_expected_*` values. A handler's in-place edit
  cannot rewrite the caller's dict or the material the oracle compares.
- Registered actions are classified with the shared `core.action_effects`
  vocabulary. Explicit read/plan declarations stay non-mutating; empty/unknown
  registered metadata is conservatively mutating; an unregistered MCP tool
  keeps its historical path (no whole-tool-surface claim).
- A normal ReAct call has only tool+params, so the server mints a stable
  logical operation id from the durable execution scope. A supplied server
  intent slot is the identity by itself (model action/material cannot re-mint
  it); without a slot, action + frozen material scope the operation inside the
  execution (identical retry dedupes, a genuinely different request is a new
  intent, not a forever payload cache). If the same action already has an
  unresolved (claimed/dispatching/uncertain) claim in the execution, a
  slotless model retry reuses that pending operation even when the model
  varies an incidental parameter; a distinct server slot or explicit operation
  id remains independent authority.
- The server operation id is carried into the handler's context copy so a
  durable producer receipt can bind to it, while caller/model args and
  result-owned expected fields stay untouched.
- `core.outbound_operation_claim` gained a generic claim over the existing
  `TaskOperationRecord` table: claim before the leaf, replay without a second
  dispatch, conflict on changed material/action, and terminal no-auto-resend
  for dispatching/uncertain states. An explicit operation id without a
  workspace/execution scope refuses before effect.
- `mark_status(expected_status=...)` is now a real database conditional UPDATE
  bound to the expected status and immutable payload digest; a peer commit
  makes it match zero rows. The legacy no-expectation caller path is unchanged
  and is not claimed as CAS.
- A succeeded claim is not fresh proof: a same-operation replay re-runs the
  independent readback. A refuted or unavailable readback returns
  `committed_unverified` / `uncertain` with identity retained and no new
  dispatch.
- `_step_act` audits an uncertain/failed mutation dict as a failure instead of
  success, so the outcome cannot slip past the string-only error check.
- `execute()` finalization reloads durable unresolved claims for the same
  execution. A cold final-answer-only pass stays `uncertain` with
  `requires_reconciliation=True`; an unreadable claim store is treated as
  unknown, not authoritative zero rows. A genuinely fresh zero-claim or
  verified run keeps its normal success, and read output is preserved.

## Verification

Fresh scratch SQLite and basetemp roots; `TESTING=1`; no live DB, world,
network, model, provider, VM, credential, install, send or spend.

- Reviewed matrix + all supplied normal-identity/reload/retry probes: **43
  passed** (`tests/test_generic_oracle_mutation_contract.py`,
  `LEAD_PROBES/test_lead_generic_draft_boundaries.py`,
  `LEAD_PROBES/test_lead_generic_normal_identity.py`,
  `LEAD_PROBES/test_lead_generic_reload_unavailable.py`,
  `LEAD_PROBES/test_lead_generic_normal_changed_retry.py`,
  `LEAD_PROBES/test_lead_generic_two_normal_writes.py`).
- Shared assignment/oracle regression command: **156 passed**.
- Generic/oracle/fleet focused cluster: **341 passed, 4 skipped**; unrelated
  baseline failures are listed in `baseline-unrelated-failures.txt`.
- Action-registry focused run: **84 passed, 2 pre-existing failures**.
- `LEAD_GENERIC_PROBE.py`: 2 passed, 1 failed. The failing test is the original
  timeout negative whose context has an explicit operation id but no
  workspace/execution. The newer confirmed probe
  `LEAD_PROBES/test_lead_generic_normal_identity.py::
  test_explicit_operation_without_workspace_cannot_dispatch` requires that
  exact path to refuse before effect, so the historical landed-row assumption
  is superseded. The tracked equivalent with complete server context
  (`test_unverified_timeout_does_not_invite_retry`) passes and proves the
  no-retry behavior against a real landed row. The original probe bytes are
  retained unchanged.
- Forced-interleaving CAS twin and fresh-session replay negative/positive
  twins are in the tracked matrix.

## Boundaries

- The doubled MCP leaf with `pre_approved=True` isolates the outcome consumer;
  it is not governance/HITL qualification.
- Unregistered MCP tools are outside this bounded classification claim.
- `core.action_effects` and `core.oracle.postcondition_verifiers` are
  Agent1-owned; they were read but not edited. Combined-source qualification
  after the PR714 main merge is owned by root/CI.
- Local harness policy denied `git merge`/`rebase` of `origin/main`
  (`e3e9d8f6c`, PR714). This evidence is bound to the disjoint branch commit;
  root owns the combined merge/qualification. The shared classifier API used
  here (`declares_mutation`, `declares_read_only`, `declares_plan_output`) is
  present and compatible in the fetched main tree.
- No whole-app GenericAgent or governance qualification is claimed.
