# `radio.create_thread` — first-DML authority linearization repair

Executed source: `7e91a3c91` (repair commit on
`codex/oracle-refresh-20261107`). Normal merge of current main `cf5e98191` at
`7a587f646`. Root's permanent first-DML test
`backend/tests/test_lead_radio_thread_authority_linearization.py` is retained
and now runs in the normal CI gate.

## Root finding

Root's decisive probe on the frozen `f29b4db12` bytes was **2 failed, 1 passed,
actual exit 1**. A peer transaction disabled the creator or a member
immediately before the first `UPDATE agent_registry` or
`INSERT agent_threads`; the candidate still committed a thread and only
refuted the authority after the effect. The earlier preflight-style/SELECT+
insert shape was insufficient.

Root originals are preserved byte-for-byte under `root-originals/`:

- `root-radio-thread-f29-first-dml.log` / `.exit.json`
- `root-radio-thread-authority-first-dml.log` / `.spec.json` / `.exit.json`
- `lead_radio_thread_authority_first_dml_frozen.py`

They are copies of root's evidence; no original was rewritten or deleted.

## Repair

The write path now performs an authority claim as the **first DML** in the same
write transaction as the thread insert:

1. Read a raw `AgentRegistry` snapshot for the creator and members:
   `id/enabled/status/workspace_id/tenant_id` (raw values, not normalized
   aliases).
2. Open the writer transaction. The first statement is a deterministic
   conditional no-op `UPDATE agent_registry` per authorized row, creator first
   then member ids sorted lexicographically. Each predicate binds the exact raw
   snapshot fields.
3. Any zero-match (or multi-match) row is a conflict: roll back before any
   `agent_threads` INSERT, return typed
   `failed_before_effect`/`proven_not_applied`, keep the peer's state, and
   create zero threads.
4. Only after every conditional claim matches does the existing
   `radio_service.create_thread` insert/commit in that same transaction.
5. The existing exact fresh-session readback and verifier remain. A peer change
   **after** the authorized commit is post-effect: replay may honestly return
   `committed_unverified`; this repair does not claim a physical stop or
   cancellation, and does not conflate the timing boundaries.
6. The accepted `core.agent_radio.radio_mutations.read_thread` helper now on
   main is imported, not duplicated. Main's send-message receipt/verifier
   machinery is reused/kept; this repair adds only the thread-specific
   producer/verifier.

No parallel engine/store/router/review scheme, role gate, or SaaS authorization
was introduced. The existing personal NULL/`default` scope compatibility and
persisted INTERN+ creator floor are preserved.

## Controls at `7e91a3c91`

All pytest ran through the shared bounded gate with fresh unique
DB/data/Lance/output and synthetic `SECRET_KEY`.

| log | result |
|---|---|
| `root-frozen-first-dml.log` (root's exact frozen probe) | **3 passed**, exit 0 |
| `focused-oracle-plus-root.log` | **32 passed**, exit 0 |
| `merged-send-registry-request.log` | **85 passed**, exit 0 |
| `radio-units.log` | **45 passed**, exit 0 |
| `heavy-full-radio.log` (`tests/test_covpush_w80a_radio.py`, heavy) | **219 passed**, exit 0 |

The heavy 219-case suite was run whole with `--profile heavy` and the 4 GiB
floor; it was not split or dropped.

Preserved controls include exact row/material, same-operation replay without a
duplicate, changed-material conflict, identity-poison resistance, changed
roster/name/tenant, missing row, duplicate operation row, rollback, readback
unavailable/mismatch, stale/moved authority, personal NULL/`default` valid
twins, persisted INTERN floor, and the original pre-implementation negative
trace.

## Registry state at this source

New-source inventory: **98 actions / 30 declared mutations / 27 covered /
3 uncovered** (`workspace.commit`, `workspace.note`, `mini_app_run`). See
`../oracle_registry_refresh_7e91a3c91/`. The earlier `908026a39` map remains
its dated historical capture (25/5); its counts were not rewritten.

## Boundaries

No live app/model/provider/account/credential/send/spend/install/deploy/VM/
PostgreSQL/sandbox. No installs. Root owns independent review, PR, CI and
merge.
