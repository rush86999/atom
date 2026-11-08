# Fix: linearize `radio.create_thread` authority as first-DML CAS

Root's first-DML probe showed a peer authority winner still produced a
committed thread on the previous candidate. This repair makes the authority
claim the first DML in the same write transaction as the thread insert:

- raw creator/member `id/enabled/status/workspace_id/tenant_id` snapshot;
- deterministic creator-first/sorted-member no-op conditional `UPDATE
  agent_registry`;
- zero-match rolls back before the thread insert and returns typed
  `proven_not_applied`; peer state preserved;
- exact-row/fresh-session verifier and existing personal NULL/`default` and
  INTERN-floor semantics retained;
- post-authorized-commit authority changes remain post-effect and may yield
  `committed_unverified`; no physical-stop claim.

Main `cf5e98191` is merged normally (`7a587f646`). Main's accepted
`radio_mutations.read_thread` and send-message helpers are reused; no parallel
engine/store/router/review scheme.

## Verification

- Root's exact frozen first-DML probe: 3 passed.
- Focused Oracle + root linearization: 32 passed.
- Merged send/registry/request group: 85 passed.
- Radio units: 45 passed.
- Full 219-case covpush radio suite (heavy, 4 GiB floor): 219 passed.

New-source registry: 98 actions / 30 mutations / 27 covered / 3 uncovered.
Old 908 map counts remain historical and unmodified.

Root owns independent review, PR, CI and merge.
