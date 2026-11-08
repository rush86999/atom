# ORACLE: verify `radio.create_thread` by exact row and current authority

## Summary

Closes the registered `radio.create_thread` postcondition gap with the existing
shared Oracle/claim/request-expectation mechanisms.

- Freezes the server-owned creator, normalized roster, name, scope and
  tenant/workspace identity; model-supplied identity args cannot override them.
- Pre-effect refuses missing/disabled/below-INTERN creators and
  missing/disabled/moved members using the existing single-tenant NULL/`default`
  scope rule.
- Re-reads the exact `AgentThread` row and material from a fresh session;
  unavailable/missing/mismatched readback stays uncertain with the known id.
- Binds the operation id in thread metadata; same-operation replay locates the
  original row, while changed material conflicts.
- Independent verifier re-checks the row, roster and current AgentRegistry
  authority; changed roster/name/tenant, stale authority, missing rows and
  duplicate operation rows are refuted.

No new engine, router, store or approval lifecycle. The send-message successor
branch and PR752 are untouched.

## Verification

- `tests/test_oracle_radio_create_thread.py`: 29 passed.
- Original failure-first probe: preserved (2 failed at predecessor), now
  2 passed on the successor.
- Affected radio units: 24 passed.
- Registry/request expectations: 59 passed.
- Radio service/adapter/server: 29 passed.
- Generic/effect-family Oracle group: 46 passed.
- Full 219-case covpush radio file: heavy gate exit 75 (not dispatched at
  <4 GiB), preserved as environmental, not a failure.

Refreshed map: 98 actions / 30 mutations / 25 covered / 5 uncovered.

## Boundaries

Scratch SQLite only; no live provider/model/account/credential/send/spend/
install/deploy/VM/Postgres/sandbox. Single-tenant semantics only. Root owns
independent review, PR, CI and merge.
