# Fix: normal-MCP `radio.create_thread` replay class (current-main merge)

Root's MCP probe failed 4/7 because `MCPService.call_tool -> action_registry`
has no Generic claim wrapper. The producer now, after the first-DML authority
CAS and before INSERT, resolves exact creator+operation rows:

- matching row -> replay original id, no second insert;
- changed material -> typed `proven_not_applied`, original retained;
- multiple historical rows -> fail closed, zero new write;
- authority loss -> pre-effect refusal with known original identity;
- readback uncertainty -> same-op retry reconciles without resend;
- missing context op id -> server-owned exact id persisted/echoed;
- caller args cannot override context identity;
- concurrent same-key writers create one winner via existing CAS/SQLite lock.

Main `8ded00232` is merged normally at `90eac34a7`; radio bytes are identical
to the parent `9c5219242` (`radio-source-identity.json`). No second claim/table/
migration/engine/router or fleet policy. Fleet adapter remains a parallel
trusted writer and is not claimed qualified for this replay contract.

## Verification

At `90eac34a7`: focused 47 passed, root frozen first-DML 3 passed, merged
send/registry/request 85 passed, radio units 45 passed. The whole 219-case
covpush radio suite passed at the radio-identical parent `9c5219242`; at
`90eac34a7` the heavy gate exited 75 (not dispatched) at 3.85 GB < 4 GiB. The
suite was not split or dropped.

Registry counts unchanged: 98 / 30 / 27 / 3.

Root owns independent review, CI and merge.
