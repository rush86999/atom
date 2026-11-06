# ORACLE-01 — sandbox caller-transaction ownership repair

Status: **submitted for independent verification.** This is the bounded repair
of the verifier's two caller-transaction loss cases on the submitted
tool-mutation sandbox writer. The original decision/material/audit controls and
the lineage/freshness repair remain; the new repair gives the sandbox result CAS
its own transaction.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-evolution-review-20261105` |
| Prior decision source | `e4816e59c` (product `eaba0cb8f`, evidence `5dc4f1b0f`) |
| Prior lineage/freshness repair | `6346cad2a` (evidence `6fbeb4ebd`) |
| Repair product source | `d4cce1625205f79412be9387f7c3fed1023d376f` |
| Executed repair source | `a39dbd12a01bbcaccaf51598f7fc586ed93926f4` |
| Accepted base | `95f7bcac1a0375b4f0465a77e15130f68fc9665d` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions and doubled sandbox; no live sandbox/model/provider |

## Finding and repair

The previous result CAS ran on the caller's `Session` and released a "clean"
caller transaction based on `Session.new/dirty/deleted`. Those collections do
not describe already-flushed writes, and the CAS's autoflush could clear the
dirty signal. Two cases lost unrelated caller work:

1. a dirty caller `User` edit was flushed by the CAS, then rolled back as
   "clean";
2. an already-flushed caller edit was rolled back at entry.

The repair:

1. The sandbox result snapshot, guarded UPDATE and commit run on a **dedicated
   owned session** bound to the engine; the caller session is never committed
   or rolled back by the operation.
2. Unflushed caller ORM work (`new/dirty/deleted`) is left untouched. The
   owned result CAS can still run; the caller commits its own edit afterwards.
3. A caller that already flushed an unrelated write is detected with a public
   SQLAlchemy `after_flush` marker. The method returns a truthful bounded
   deferred/skipped result before dispatch, preserving the caller transaction.
4. A clean caller read transaction is released only after the authoritative
   snapshot is read, so the owned writer is not blocked; this releases no
   writes.
5. The caller's identity map is expired after a successful owned commit only
   when the caller is clean and has no pending/flushed work.
6. Review decisions committed before dispatch still cause zero sandbox calls;
   a review arriving while the worker runs still wins the result CAS.

## Effect and result states

- `verified`: owned CAS matched the exact id/tenant/prior status/tool/parent
  lineage/code/prior error; passed/failed committed on the owned session.
- `skipped`: review/status changed, material changed, missing target, or a
  flushed caller transaction prevented safe independent execution. The caller
  session and peer state are preserved.
- Deferred/skipped result reason `caller_transaction_pending` is truthful: the
  caller must commit or roll back its own work before retrying; the operation
  did not dispatch or record a result.
- The caller's unrelated pending edit is not committed by the sandbox; a fresh
  session sees the old value until the caller commits.

## Caller / parallel-writer map

| Caller or consumer | Action |
|---|---|
| `sandbox_execute_mutation` | owned session for snapshot/result CAS/commit |
| caller `Session` | never committed/rolled back by the sandbox; clean read transaction may be released; unflushed/flushed work preserved |
| review decision routes | durable approved/rejected; pre-dispatch zero calls |
| `ToolMutation` row | exact material CAS; peer/reviewer wins |
| `AuditLog` | unchanged receipts from the decision routes |

## Controls

- **Verifier probes: 5 passed** (`probes-314.log`): the original changed-lineage
  and stale-approved/rejected probes plus the two caller-work loss probes.
- **Focused: 65 passed on Python 3.14 and 3.11** (`focused-314.log`,
  `focused-311.log`): the prior 58 controls plus 7 caller-transaction twins.
- **Affected evolution: 311 passed, 29 skipped, 1 exact baseline failure on both
  versions** (`affected-evolution-314.log`, `affected-evolution-311.log`).
  Baseline `9d73552d2`... `95f7bcac1` has the same single
  `test_reflection_engine` pattern-detection failure (`baseline-evolution-*.log`).
- **Affected review/audit: 111 passed on both versions**
  (`affected-review-audit-314.log`, `affected-review-audit-311.log`).

The new twins cover dirty and flushed caller edits, caller-commit timing, new
and deleted caller objects, a clean caller read transaction, and deferred
flushed-caller dispatch. They assert real fresh-session caller data and that
the sandbox did not commit it early.

## Boundaries

- No physical cancellation of an in-flight worker; a review arriving during the
  worker wins the result CAS.
- No live sandbox/Docker/model/provider/credential/spend/send/download/
  deployment operation.
- No new status, worker, review, operation or transaction engine.
- PostgreSQL runtime/soak, multi-worker qualification and whole-app ORACLE-01
  remain open.
- The accepted admin/2FA/canvas/ORCH-01/feedback/wait/employee lanes and the
  repaired memory/skill branches remain independent.

## Artifacts

`probes-314.log`, `focused-*.log`, `affected-evolution-*.log`,
`affected-review-audit-*.log`, `baseline-evolution-*.log`, `source-tree.txt`,
`README.md`, `TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and source file.
