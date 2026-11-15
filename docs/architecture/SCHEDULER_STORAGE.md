# Scheduler job-store storage anchoring

The workflow scheduler uses APScheduler's `SQLAlchemyJobStore`. Its default
configuration (`core.config.SchedulerConfig`) is:

```
SCHEDULER_JOB_STORE_TYPE=sqlalchemy
SCHEDULER_JOB_STORE_URL=sqlite:///jobs.sqlite
```

SQLAlchemy treats that relative file URL as **CWD-relative**. Before this
fix, launching uvicorn from the repo root and from `backend/` produced two
different stores (`<repo>/jobs.sqlite` and `backend/jobs.sqlite`): a job
scheduled in one launch was invisible in the other.

## Canonical location

The scheduler resolves the URL through the same helper the database uses
(`core.local_paths.anchor_sqlite_url`):

| Configured URL | Effective store |
|---|---|
| `sqlite:///jobs.sqlite` (default) | `<backend>/jobs.sqlite` |
| `sqlite:///./jobs.sqlite` | `<backend>/jobs.sqlite` |
| `sqlite+pysqlite:///jobs.sqlite` | `<backend>/jobs.sqlite` |
| `sqlite:////absolute/path/jobs.sqlite` | unchanged |
| `sqlite:///:memory:` / `sqlite://` | unchanged (in-memory) |
| `sqlite:///file:...?...uri=true` | unchanged (SQLite `file:` URI) |
| `postgresql://...`, `redis://...` | unchanged |

A relative **override** (`SCHEDULER_JOB_STORE_URL=sqlite:///my-jobs.sqlite`)
is anchored to `backend/` as well, so it no longer depends on the launch CWD.
Absolute overrides remain authoritative. Anchoring happens when the scheduler
is constructed (`ai.workflow_scheduler.WorkflowScheduler`), not when
`SchedulerConfig` is created, so importing configuration cannot create or
move a store.

## Legacy adoption (startup only)

A root launch before this fix may have written `<repo>/jobs.sqlite`. Stop
all legacy backend/scheduler writers before adoption. Sidecar checks detect
observed transactions; they are not a process-exclusivity lock. At backend
startup, immediately before the scheduler opens its store,
`core.scheduler_store.reconcile_scheduler_job_store` runs:

* canonical absent, legacy regular file present, unambiguous → the legacy
  bytes are copied to the canonical path with an exclusive, no-clobber
  hardlink; the copy is sha256-verified. **The original legacy file is left
  untouched.** If the filesystem cannot provide an atomic no-clobber hardlink,
  adoption is refused; there is no direct-copy fallback that could publish a
  partial canonical file on a disk-full error.
* canonical present and legacy absent → canonical is used.
* canonical present **and** legacy present → automatic selection is refused
  (`SchedulerStoreConflict`, CRITICAL log); both files are preserved
  untouched. This is deliberate: automatically using canonical could hide an
  intact legacy store that contains the real jobs.
* neither present → fresh install; the scheduler creates the canonical file.
* legacy exists as a symlink, directory or other non-regular file → startup
  refuses adoption with a CRITICAL log (`SchedulerStoreConflict`); no guess is
  made.
* legacy has `-wal`/`-shm`/`-journal` sidecars (uncheckpointed / still open) →
  adoption is refused; stop the old backend and let SQLite checkpoint/close it
  first. The sidecars are checked again after the temp copy, before install,
  to refuse newly observed writer activity. This does not replace stopping
  all legacy writers before adoption.

After an automatic adoption, the original remains at the legacy path. Verify
the adopted jobs, stop the backend, and archive that original outside the
known store paths before the next startup. Otherwise both files are present
and the next startup deliberately refuses the conflict; it does not silently
ignore the preserved legacy copy.

Reconciliation never runs from configuration import or from ordinary
`SchedulerConfig` construction. `core/scheduler_store.py` also exposes
`scheduler_job_store_status()` for read-only diagnostics.

### Operator resolution for a conflict

If both files exist, startup refuses to choose. Decide deliberately:

1. Stop the backend.
2. Inspect both files (they are SQLite databases; e.g. `sqlite3
   <file> 'select id from apscheduler_jobs'`). Do not delete either yet.
3. Keep the authoritative file at `<backend>/jobs.sqlite`; archive or rename
   the other one outside the store path.
4. Restart. No automatic merge occurs.
5. While the conflict is unresolved, the scheduler is not started and the
   schedule/list/remove methods return `SchedulerStoreUnavailable` (HTTP 503
   for the served routes), so no RAM-only job is acknowledged and no empty
   store is presented as authoritative.

This is intentionally a one-file reconciliation, not a migration framework.
Historical job ids that were written under the old root launch are preserved
in the legacy file for audit; they are not silently merged.

## Shared SQLite target and backup safety

The main database test-safety guard and backup/fingerprint service use
`core.local_paths.resolve_sqlite_file_path`. It follows SQLAlchemy's actual
SQLite connection arguments, then SQLite's URI parsing and decoding. It does
not substitute an intended raw-URL filename for the file the engine opens.
This matters for encoded `#`, `?` and `%` characters and URI query parameters.
Named-memory databases are excluded only when the actual connection uses
memory; a plain SQLite URL with an ignored `mode=memory` query can still be a
disk file. Relative explicit `file:` URIs retain SQLite's CWD semantics;
use an absolute URL when the configured location must be stable.

`core.db_safety` consumes the same resolved target. Its read-only URI builder
percent-encodes filesystem paths, so filename characters cannot swallow
`mode=ro` or open a different writable sibling. Existing SQLite backup,
integrity/count verification and failure-preserves-old-snapshots behavior
remain in place. Engine URLs are not rewritten by this target resolver.

## Refused-store availability

When startup refuses the store (conflict, ambiguous legacy, failed adoption,
or scheduler start failure), `core.scheduler_store` records a process-local
failed state. `WorkflowScheduler.schedule_workflow*`, `list_jobs`,
`remove_schedule`/`remove_job` and `reschedule_system_pipelines` consult the
shared `require_scheduler_store_ready()` guard, so every consumer refuses
instead of acknowledging an in-memory job or an empty authoritative list. The
served schedule/list/remove routes translate that exception to HTTP 503 with a
generic actionable `detail` and stable `code=SCHEDULER_STORE_UNAVAILABLE`; the
detailed conflict/adoption reason stays in the server log, not the caller
response. The chat scheduling handler returns `success: false`.

## References

* SQLAlchemy SQLite dialect — connect strings / relative paths and
  `file:` URI mode:
  <https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#connect-strings>
* APScheduler `SQLAlchemyJobStore` — job store URL and persistence:
  <https://apscheduler.readthedocs.io/en/3.x/modules/jobstores/sqlalchemy.html>

