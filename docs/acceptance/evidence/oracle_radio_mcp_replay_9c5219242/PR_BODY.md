# Fix: normal-MCP `radio.create_thread` replay class

Root's MCP probe failed 4/7 because `MCPService.call_tool -> action_registry`
has no Generic claim wrapper. The producer now resolves replay after the
first-DML authority CAS and before the thread insert:

- exact creator+operation rows from thread metadata;
- one matching row -> original id replayed, no second insert;
- changed material -> typed `proven_not_applied` with original retained;
- multiple historical rows -> fail closed, zero new write, rows retained;
- authority loss -> pre-effect refusal with known original identity;
- readback uncertainty -> same-op retry reconciles the original row;
- missing context operation id -> server-owned exact id persisted/echoed;
- caller args never override trusted context identity;
- concurrent same-key writers use the existing authority CAS/SQLite lock and
  create one winner.

No second Generic claim, new table/migration/ledger/engine/router, or fleet
policy. `read_thread` is reused from main. Fleet adapter remains a parallel
trusted writer and is not claimed qualified for this replay contract.

## Verification at 9c5219242

- Focused (create Oracle + root authority + root MCP + replay matrix): 47 passed.
- Root frozen first-DML: 3 passed.
- Merged send/registry/request: 85 passed.
- Radio units: 45 passed.
- Full 219-case covpush radio heavy suite: 219 passed.

Registry counts unchanged: 98 / 30 / 27 / 3. Old maps remain historical.

Root owns independent review, CI and merge.
