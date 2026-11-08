#!/usr/bin/env python3
"""Seed one synthetic scratch world for the prepared child restore smoke.

NOT EXECUTED by the code-only worker. This is a disclosed
PRODUCT_MODEL_READBACK_FIXTURE, not a real agent or business work product. It
uses the product models and the product password hasher, creates real DOCX,
text and Parquet files, and writes only synthetic ids/paths.

The harness passes an explicit ``--repo-root`` so moving this file cannot
silently change which backend is seeded. ``TESTING=0`` is pinned before product
imports because the child must use the explicit scratch target database rather
than core.database's TESTING=1 reroute.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

SCRATCH_PARENT = Path("/private/tmp")
OFFICE_TEXT = "child restore smoke office artifact\nsecond disclosure line"
DOCUMENT_TEXT = "child restore smoke document text\n"
CANVAS_TITLE = "Child restore smoke office"
FORBIDDEN_AUTHORITY_KEYS = (
    "operation_id", "review_status", "evidence_refs", "postconditions",
    "success", "verification", "approval", "reviewer", "receipt", "operation",
)
FORBIDDEN_MARKERS = (
    "synthetic-seed-operation", "synthetic-old-approver",
    "synthetic-old-verifier", "synthetic-old-reviewer",
    "synthetic-receipt", "synthetic-receipt-id",
)
PROVIDER_ENV_KEYS = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY", "GROQ_API_KEY",
    "TOGETHER_API_KEY", "AZURE_OPENAI_API_KEY", "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY", "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET",
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "STRIPE_SECRET_KEY",
    "SENDGRID_API_KEY", "TWILIO_AUTH_TOKEN", "TELEGRAM_BOT_TOKEN",
    "DISCORD_BOT_TOKEN", "SLACK_BOT_TOKEN",
)


class SeedError(RuntimeError):
    """A safe refusal in the synthetic fixture seed."""


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _symlink_component(path: Path):
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            return current
    return None


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd = os.open(str(path), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def _read_synthetic_password(path: Path) -> str:
    try:
        st = path.stat()
    except OSError as exc:
        raise SeedError(f"password file is unavailable: {exc}") from exc
    if not stat.S_ISREG(st.st_mode):
        raise SeedError("password file is not a regular file")
    if stat.S_IMODE(st.st_mode) & 0o077:
        raise SeedError("password file mode must be 0600")
    password = path.read_text(encoding="utf-8").strip()
    if len(password) < 16:
        raise SeedError("synthetic password is too short")
    return password


def _validate_source_root(source: Path) -> None:
    if not source.is_absolute():
        raise SeedError("source root must be absolute")
    if not _is_within(source, SCRATCH_PARENT) or source.resolve() == SCRATCH_PARENT.resolve():
        raise SeedError("source root must be a fresh child under /private/tmp")
    bad = _symlink_component(source)
    if bad is not None:
        raise SeedError(f"source root contains a symlink component: {bad}")
    if source.exists():
        if not source.is_dir():
            raise SeedError("source root exists and is not a directory")
        if any(source.iterdir()):
            raise SeedError(f"source root is not empty: {source}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--ids-out", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    if not (repo_root / "backend" / "main_api_app.py").is_file():
        raise SeedError(f"repo root does not contain backend/main_api_app.py: {repo_root}")
    if not (repo_root / "backend" / "core" / "models.py").is_file():
        raise SeedError(f"repo root does not contain backend/core/models.py: {repo_root}")
    source = Path(args.source_root).expanduser()
    _validate_source_root(source)
    source = source.resolve()
    ids_out = Path(args.ids_out).expanduser()
    if not ids_out.is_absolute() or not _is_within(ids_out, source.parent):
        raise SeedError("ids-out must be an absolute file under the scratch root")
    password = _read_synthetic_password(Path(args.password_file).expanduser())

    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        raise SeedError("SECRET_KEY must be supplied by the harness (do not persist a dev key)")

    # Pin the synthetic scratch world before importing any product module.
    for name in PROVIDER_ENV_KEYS:
        os.environ.pop(name, None)
    os.environ.update({
        "TESTING": "0",
        "ENVIRONMENT": "test",
        "SECRET_KEY": secret_key,
        "DATABASE_URL": f"sqlite:///{source / 'atom.db'}",
        "ATOM_DATA_DIR": str(source),
        "ATOM_OFFICE_DIR": str(source / "office"),
        "ATOM_EMAIL_ATTACHMENT_DIR": str(source / "email_attachments"),
        "LANCEDB_URI": str(source / "atom_memory"),
        "LANCEDB_URI_BASE": str(source / "atom_memory"),
        "ATOM_OUTPUT_DIR": str(source / "output"),
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ATOM_AGENT_EVOLUTION_ENABLED": "false",
        "ATOM_CHAT_STREAMING": "false",
        "MEMORY_CONSOLIDATION_ENABLED": "false",
        "ENABLE_EMAIL_ATTACHMENT_MEMORY_INDEX": "false",
        "ENABLE_BINARY_INGESTION": "false",
        "ATOM_DEPLOYMENT_AUDIENCE": "development",
        "ATOM_EMAIL_SEND_DISABLED": "true",
        "ATOM_ASSIGNMENT_ALLOW_LIVE_SEND": "false",
        "PYTHONDONTWRITEBYTECODE": "1",
    })

    source.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in ("office", "office/uploads", "email_attachments",
                 "sheet_datasets/default/ds-1", "atom_memory", "output",
                 "basetemp", "docs"):
        (source / name).mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(repo_root / "backend"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.models  # noqa: F401 - register all models
    from core.auth import get_password_hash
    from core.models import (
        Canvas,
        CanvasAudit,
        DatasetEntry,
        GoalObjective,
        IngestedDocument,
        Tenant,
        User,
        UserRole,
        Workspace,
    )
    from core.models_registration import Base
    from docx import Document
    import pandas as pd

    office_file = source / "office" / "restored-office.docx"
    doc = Document()
    for line in OFFICE_TEXT.splitlines():
        doc.add_paragraph(line)
    doc.save(office_file)
    office_sha = hashlib.sha256(office_file.read_bytes()).hexdigest()

    document_file = source / "office" / "uploads" / "restored-document.txt"
    document_file.write_text(DOCUMENT_TEXT, encoding="utf-8")
    document_sha = hashlib.sha256(document_file.read_bytes()).hexdigest()

    parquet_file = source / "sheet_datasets" / "default" / "ds-1" / "sheet.parquet"
    pd.DataFrame({"value": [1, 2]}).to_parquet(parquet_file, index=False)
    parquet_bytes = parquet_file.read_bytes()
    parquet_sha = hashlib.sha256(parquet_bytes).hexdigest()
    parquet_content_hash = hashlib.sha1(parquet_bytes).hexdigest()

    email = "child-restore-smoke@example.invalid"
    tenant_id = "tenant-child-smoke"
    workspace_id = "ws-child-smoke"
    user_id = "user-child-smoke"
    canvas_id = "canvas-child-smoke"
    audit_id = "audit-child-smoke"
    goal_id = "goal-child-smoke"
    document_id = "document-child-smoke"
    dataset_id = "dataset-child-smoke"
    role = UserRole.MEMBER.value

    content = {
        "office_file": str(office_file),
        "file_path": str(office_file),
        "format": "docx",
    }
    historical_details = {
        "content": content,
        "canvas_type": "office_word",
        "component": "office",
        "component_type": "rich_editor",
        "component_name": "Office Word",
        "title": CANVAS_TITLE,
        "type_pinned": True,
        "draft": {
            "draft_id": "fixture-draft",
            "to_emails": ["fixture@example.invalid"],
            "body": "fixture draft body",
            "approved_by": "synthetic-old-approver",
        },
        "operation_id": "synthetic-seed-operation",
        "review_status": "accepted",
        "evidence_refs": ["synthetic-receipt"],
        "postconditions": ["synthetic-postcondition"],
        "success": True,
        "verification": {
            "status": "verified",
            "verifier": "synthetic-old-verifier",
        },
        "approval": {
            "approved_by": "synthetic-old-approver",
            "status": "approved",
        },
        "reviewer": "synthetic-old-reviewer",
        "receipt": {"receipt_id": "synthetic-receipt"},
        "operation": {
            "operation_id": "synthetic-seed-operation",
            "status": "succeeded",
        },
    }

    engine = create_engine(f"sqlite:///{source / 'atom.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add(Tenant(
            id=tenant_id, name="Child Restore Smoke Tenant",
            subdomain="child-restore-smoke", edition="personal",
            is_active=True,
        ))
        db.flush()
        db.add(Workspace(
            id=workspace_id, name="Child Restore Smoke Workspace",
            tenant_id=tenant_id, status="active",
        ))
        db.flush()
        db.add(User(
            id=user_id, email=email,
            hashed_password=get_password_hash(password),
            first_name="Restore", last_name="Smoke", role=role,
            status="active", tenant_id=tenant_id, workspace_id=workspace_id,
            is_active=True,
        ))
        db.flush()
        db.add(Canvas(
            id=canvas_id, tenant_id=tenant_id, workspace_id=workspace_id,
            created_by=user_id, name=CANVAS_TITLE, canvas_type="office_word",
            content=content, status="active",
        ))
        db.flush()
        db.add(CanvasAudit(
            id=audit_id, canvas_id=canvas_id, tenant_id=tenant_id,
            action_type="update", user_id=user_id, agent_id=None,
            canvas_type="office_word", details_json=historical_details,
        ))
        db.add(IngestedDocument(
            id=document_id, workspace_id=workspace_id, tenant_id=tenant_id,
            file_name=document_file.name, file_path=str(document_file),
            file_type="txt", integration_id="upload",
            external_id=document_id,
            file_size_bytes=document_file.stat().st_size,
            content_preview=DOCUMENT_TEXT,
        ))
        db.add(DatasetEntry(
            id=dataset_id, workspace_id=workspace_id, tenant_id=tenant_id,
            created_by=user_id, source_kind="file", source="upload",
            external_id=dataset_id, file_name=parquet_file.name,
            content_hash=parquet_content_hash, entity_name="Sheet1",
            dataset_name="sheet_smoke", parquet_path=str(parquet_file),
            row_count=2, column_count=1, columns_json=["value"],
            status="active",
        ))
        db.add(GoalObjective(
            id=goal_id, tenant_id=tenant_id, workspace_id=workspace_id,
            title="Child restore smoke goal",
            description=(
                "Synthetic readback fixture only; not business completion."),
            status="active", progress=0.0, criteria=[], key_results=[],
            metadata_json={
                "seed": "child_restore_smoke",
                "fixture_class": "PRODUCT_MODEL_READBACK_FIXTURE",
                "business_completion_claimed": False,
                "real_agent_or_business_work": False,
            },
            owner_id=user_id, source="api",
        ))
        db.commit()
    engine.dispose()

    con = sqlite3.connect(f"file:{(source / 'atom.db').resolve().as_posix()}?mode=ro",
                          uri=True)
    try:
        raw_details = con.execute(
            "SELECT details_json FROM canvas_audit WHERE id=?", (audit_id,)
        ).fetchone()[0]
    finally:
        con.close()
    audit_details_sha = hashlib.sha256(str(raw_details).encode("utf-8")).hexdigest()

    ids = {
        "schema": "atom-child-restore-ids-2",
        "fixture_class": "PRODUCT_MODEL_READBACK_FIXTURE",
        "business_completion_claimed": False,
        "real_agent_or_business_work": False,
        "seeded_role": role,
        "role_source": "core.models.UserRole.MEMBER.value",
        "source_root": str(source),
        "source_office_root": str(source / "office"),
        "email": email,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "canvas_id": canvas_id,
        "audit_id": audit_id,
        "goal_id": goal_id,
        "document_id": document_id,
        "dataset_id": dataset_id,
        "canvas_title": CANVAS_TITLE,
        "canvas_type": "office_word",
        "office_artifact_path": str(office_file),
        "office_artifact_sha256": office_sha,
        "office_artifact_text": OFFICE_TEXT,
        "document_file_path": str(document_file),
        "document_sha256": document_sha,
        "document_text": DOCUMENT_TEXT,
        "parquet_path": str(parquet_file),
        "parquet_sha256": parquet_sha,
        "parquet_rows": [[1], [2]],
        "parquet_columns": ["value"],
        "audit_details_sha256": audit_details_sha,
        "forbidden_authority_keys": list(FORBIDDEN_AUTHORITY_KEYS),
        "forbidden_markers": list(FORBIDDEN_MARKERS),
        "memory": {
            "included": False,
            "lancedb_search_claimed": False,
            "public_document_search_claimed": False,
        },
        "public_routes": {
            "login": "POST /api/auth/login",
            "me": "GET /api/auth/me",
            "canvas": "GET /api/canvas/{canvas_id}",
            "goal": "GET /api/goals/{goal_id}",
            "office_download": "GET /api/v1/office/download",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(Path(args.ids_out).expanduser(), ids)
    print(json.dumps(ids, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SeedError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(2)
