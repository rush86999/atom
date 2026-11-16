# PostgreSQL full-app HTTP restart — November 16, 2026

At public product source `c1ab1af1da0600f6bc91199b7569d5756ce64492`, the canonical
`main_api_app:app` passed normal public registration/login, owned blank-canvas
creation/readback, unauthenticated denial (401), then a fresh API process,
normal login again and readback of the same canvas ID and title. Both API
processes stopped and the exact owned PostgreSQL container was removed.

The database was independently verified empty before the installer schema
adoption path created all 371 registered tables and stored all seven original
Alembic heads in a 255-character version column. It used a new PostgreSQL
15.19 container with memory-backed storage, no host volume, 384 MiB and one
CPU. The cached Python 3.12.13 virtual environment and controlled test mode
were used. No authentication override, provider/model inference, dependency
installation, existing database or owner app was involved.

The OS network guard admitted only the two owned loopback ports. Independent
listener controls, including native libpq connections, proved the allowed
ports were reached and another disposable listener was not. Foreign/owner
ports and external connections were denied. Child cleanup used only live,
unreaped process handles in their own process groups; no port-based cleanup.

Three earlier cases are retained: interpreter symlink resolution accidentally
selected system Python before app startup; a health probe used the wrong
schema path; and the email validator rejected a synthetic `.invalid` domain.
All earlier owned containers were removed. Local source-schema validation
confirmed the corrected registration/login/canvas bodies before the passing
case. No failed or uncertain mutation was retried in place.

This qualifies API-process restart persistence for this source and journey.
It does not qualify database-container restart, persistent-volume durability,
asyncpg transport, multiworker operation, soak, backup/restore, existing
database upgrades, ordinary frontend journeys, model quality or production
readiness. Optional automation-settings initialization attempted a hardcoded
source-tree write denied by the read-only guard; settings persistence was not
claimed. The original 143 claims/18 goals and historical score are unchanged.

The accompanying filtered result records statuses and scope without tokens,
passwords, database connection strings or live application data.

[Filtered result](evidence/postgresql_fullapp_restart_20261116/result.json).
