"""Run the REAL alembic upgrade against a predecessor scratch database.

Builds the minimal pre-migration world an older install has: a
``task_operation_records`` table without ``result_json``, an old succeeded
claim row, and ``alembic_version`` stamped at the parent revision. The real
alembic ``upgrade`` command then runs in a subprocess (so the local
``backend/alembic`` scripts directory cannot shadow the installed package).

Checks: the chosen revision is recorded, the old claim is retained with a NULL
receipt, the new column is nullable, and a second upgrade is an idempotent
no-op. This is a SQLite execution only; no PostgreSQL runtime claim is made.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
SCRATCH = Path(__file__).resolve().parent / "scratch"
DB = SCRATCH / "upgrade.db"
PARENT = "a2f0c1d4e5b6"
REVISION = "20261107_task_operation_result"
OPERATION_ID = "op-pre-migration-claim"

SCRATCH.mkdir(parents=True, exist_ok=True)
if DB.exists():
    DB.unlink()

with sqlite3.connect(DB) as raw:
    raw.execute("""
        create table task_operation_records (
            id varchar primary key,
            created_at datetime,
            updated_at datetime,
            workspace_id varchar not null,
            tenant_id varchar,
            run_id varchar not null,
            idempotency_key varchar not null,
            payload_sha256 varchar not null,
            operation_id varchar not null,
            operation_type varchar not null,
            status varchar not null
        )
    """)
    raw.execute("""
        insert into task_operation_records (
            id, workspace_id, tenant_id, run_id, idempotency_key,
            payload_sha256, operation_id, operation_type, status
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "record-pre-migration", "ws-shop", "tenant-shop", "exec-shop",
        OPERATION_ID, "a" * 64, OPERATION_ID, "generic:agent:shopify_create_product",
        "succeeded",
    ))
    raw.execute(
        "create table alembic_version (version_num varchar(32) not null)")
    raw.execute(
        "insert into alembic_version (version_num) values (?)", (PARENT,))
    raw.commit()


def run_upgrade() -> None:
    environment = os.environ.copy()
    environment.update({
        "TESTING": "1",
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite:///{DB}",
        # core.database substitutes backend/test_integration.db under
        # TESTING=1 unless its pytest-scratch guard sees an explicit non-dev
        # URL. Mark this as a scratch run so the explicit URL is honored.
        "PYTEST_CURRENT_TEST": "scratch-migration-upgrade",
    })
    environment.pop("PYTHONPATH", None)
    runner = (
        "import sys\n"
        "sys.path = [p for p in sys.path if p not in ('', '.') "
        "and not p.rstrip('/').endswith('/backend')]\n"
        "from alembic.config import main\n"
        "main()\n"
    )
    result = subprocess.run(
        [
            sys.executable, "-c", runner,
            "-c", str(BACKEND / "alembic.ini"),
            "upgrade", REVISION,
        ],
        cwd=str(SCRATCH),
        env=environment,
        capture_output=True,
        text=True,
        timeout=240,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout + "\n" + result.stderr)
        raise SystemExit(result.returncode)


def state():
    with sqlite3.connect(DB) as raw:
        versions = [
            row[0] for row in raw.execute(
                "select version_num from alembic_version order by version_num")
        ]
        columns = {
            row[1]: row[3] for row in raw.execute(
                "pragma table_info(task_operation_records)")
        }
        claim = raw.execute(
            "select status, payload_sha256, result_json "
            "from task_operation_records where operation_id = ?",
            (OPERATION_ID,),
        ).fetchone()
    return versions, columns, claim


run_upgrade()
versions, columns, claim = state()
assert versions == [REVISION], versions
assert "result_json" in columns, columns
assert columns["result_json"] == 0, columns
assert claim == ("succeeded", "a" * 64, None), claim
print(f"upgrade recorded {REVISION!r}; old succeeded claim retained (NULL receipt)")

run_upgrade()
versions, columns, claim = state()
assert versions == [REVISION], versions
assert claim == ("succeeded", "a" * 64, None), claim
print("second upgrade is an idempotent no-op (one version row, claim unchanged)")
print("scratch existing-database upgrade verified on SQLite only")
