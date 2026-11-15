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

A root launch before this fix may have written `<repo>/jobs.sqlite`. At
backend startup, immediately before the scheduler opens its store,
`core.scheduler_store.reconcile_scheduler_job_store` runs:

* canonical absent, legacy regular file present, unambiguous → the legacy
  bytes are copied to the canonical path with an exclusive, no-clobber
  hardlink; the copy is sha256-verified. **The original legacy file is left
  untouched.**
* canonical present → it wins. If a legacy file also exists, a CRITICAL log
  names both paths and the legacy file is preserved. Nothing is merged or
  overwritten.
* neither present → fresh install; the scheduler creates the canonical file.
* legacy exists as a symlink, directory or other non-regular file → startup
  refuses adoption with a CRITICAL log (`SchedulerStoreConflict`); no guess is
  made.

Reconciliation never runs from configuration import or from ordinary
`SchedulerConfig` construction. `core/scheduler_store.py` also exposes
`scheduler_job_store_status()` for read-only diagnostics.

### Operator resolution for a conflict

If both files exist, decide deliberately:

1. Stop the backend.
2. Inspect both files (they are SQLite databases; e.g. `sqlite3
   <file> 'select id from apscheduler_jobs'`). Do not delete either yet.
3. Keep the authoritative file at `<backend>/jobs.sqlite`; archive or rename
   the other one outside the store path.
4. Restart. The scheduler uses the canonical file; no automatic merge occurs.

This is intentionally a one-file reconciliation, not a migration framework.
Historical job ids that were written under the old root launch are preserved
in the legacy file for audit; they are not silently merged.

## References

* SQLAlchemy SQLite dialect — connect strings / relative paths and
  `file:` URI mode:
  <https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#connect-strings>
* APScheduler `SQLAlchemyJobStore` — job store URL and persistence:
  <https://apscheduler.readthedocs.io/en/3.x/modules/jobstores/sqlalchemy.html>

