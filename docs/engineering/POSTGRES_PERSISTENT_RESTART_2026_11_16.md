# PostgreSQL persistent-volume restart — November 16, 2026

A new isolated PostgreSQL 15 container survived a real normal restart with its
named volume. At published source `3316b0fe71a1203a90e0f4ec856d7eb5a08d2f4a`,
fresh API processes logged in and read the same previously created canvas
after the database restarted. This is bounded operations evidence, not full
PostgreSQL or Goal 16 acceptance.

## Observed boundary

The empty database used the existing fresh-schema installer path. Normal
public registration, login, canvas creation and readback passed; an unsigned
read returned 401. A second API process logged in and read the same canvas.
Both writers were stopped before the database snapshot and restart.

Exactly one restart targeted the owned container ID. Container/image identity,
database system identifier, database/role and the complete named-volume
identity remained unchanged; the database postmaster start time advanced.
All 372 public tables, row counts and canonical content fingerprints matched
before and after. Seven migration heads and the 255-character revision column
were intact. The retained comparison includes 18 total rows in this synthetic
world; it is not a scale test.

After restart, two further API processes independently performed normal login
and read the same canvas without registering the account or creating the
canvas again. The unsigned-read control remained 401. All four API processes
were confirmed absent afterward. The exact owned container and volume were
removed only after writer shutdown and ownership/reference checks; independent
read-only checks confirmed their absence. Existing PostgreSQL/Redis test
containers retained their original IDs and volumes and remained healthy.

## Method and retained evidence

[The filtered receipt](evidence/postgres_persistent_restart_20261116/result.json)
retains source/verifier hashes, exact data comparisons, API outcomes and cleanup
scope. The test used synchronous psycopg2/SQLAlchemy, generated isolated
credentials in memory, controlled test mode, OS-enforced network restrictions
and no external model or integration requests. It did not use the live dev DB.
The helper had 25 offline tests, independent identity/storage negative controls
and seven cleanup controls before this fresh case. A new OS network preflight
proved only its owned PostgreSQL/API ports were reachable.

An earlier case failed before its container, app or database started when the
portable drive was disconnected. That failure and its one-shot claim remain
retained. After the drive identity was verified, normal Docker recovery
restored healthy original services. The previously ambiguous volume was absent;
no deletion or reset was needed. This successful case used a new root and claim.

## Remaining scope

This does not verify historical schema upgrades, asyncpg, cluster roles,
replication/failover, PITR, physical backup, concurrent/multiworker or production
workloads. A normal container restart does not establish abrupt host power-loss
or drive-removal safety. The completed case must never be rearmed. Original
143 claims and all 18 goals remain unchanged.
