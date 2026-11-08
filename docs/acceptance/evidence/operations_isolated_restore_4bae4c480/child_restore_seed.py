#!/usr/bin/env python3
"""Seed an ordinary scratch world for the child restore smoke.

NOT EXECUTED by the 4bae4c480 candidate.  This is an evidence-packet harness for
root to run after cleaning disk headroom.  It seeds ordinary product-model rows
in a scratch database; it does not call a provider, send anything, or claim
business completion.  The seeded assignment/goal rows are labeled fixtures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--ids-out", required=True)
    args = ap.parse_args()

    source = Path(args.source_root).expanduser().resolve()
    if source.exists() and any(source.iterdir()):
        raise SystemExit(f"REFUSED: source root is not empty: {source}")
    for name in ("office", "office/uploads", "email_attachments",
                 "sheet_datasets", "atom_memory", "output", "basetemp"):
        (source / name).mkdir(parents=True, exist_ok=True)
    password = Path(args.password_file).read_text().strip()
    if not password:
        raise SystemExit("REFUSED: empty synthetic password")

    # Pin the scratch world before importing product modules.  This is a
    # scratch source world, never the live dev DB.
    os.environ.update({
        "TESTING": "0",
        "ENVIRONMENT": "test",
        "SECRET_KEY": "synthetic-child-restore-smoke",
        "DATABASE_URL": f"sqlite:///{source / 'atom.db'}",
        "ATOM_DATA_DIR": str(source),
        "ATOM_OFFICE_DIR": str(source / "office"),
        "ATOM_EMAIL_ATTACHMENT_DIR": str(source / "email_attachments"),
        "LANCEDB_URI": str(source / "atom_memory"),
        "LANCEDB_URI_BASE": str(source / "atom_memory"),
        "ATOM_OUTPUT_DIR": str(source / "output"),
    })

    backend = Path(__file__).resolve().parents[4] / "backend"
    sys.path.insert(0, str(backend))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.models  # noqa: F401 - register all models
    from core.auth import get_password_hash
    from core.models import (
        Canvas,
        CanvasAudit,
        GoalObjective,
        IngestedDocument,
        Tenant,
        User,
        Workspace,
    )
    from core.models_registration import Base

    from docx import Document

    office_dir = source / "office"
    office_file = office_dir / "restored-office.docx"
    doc = Document()
    doc.add_paragraph("child restore smoke office artifact")
    doc.save(office_file)
    artifact_sha = hashlib.sha256(office_file.read_bytes()).hexdigest()

    document_file = office_dir / "uploads" / "restored-document.txt"
    document_file.write_text("child restore smoke document text\n")
    document_sha = hashlib.sha256(document_file.read_bytes()).hexdigest()

    engine = create_engine(f"sqlite:///{source / 'atom.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    email = "restore-smoke@example.invalid"
    with Session() as db:
        db.add(Tenant(id="tenant-smoke", name="Smoke Tenant",
                      subdomain="restore-smoke"))
        db.flush()
        db.add(Workspace(id="ws-smoke", name="Smoke Workspace",
                         tenant_id="tenant-smoke"))
        db.flush()
        db.add(User(
            id="user-smoke", email=email,
            hashed_password=get_password_hash(password),
            first_name="Restore", last_name="Smoke", role="owner",
            status="active", tenant_id="tenant-smoke",
            workspace_id="ws-smoke", is_active=True,
        ))
        db.flush()
        content = {
            "office_file": str(office_file),
            "file_path": str(office_file),
            "format": "docx",
        }
        db.add(Canvas(
            id="canvas-smoke", tenant_id="tenant-smoke",
            workspace_id="ws-smoke", created_by="user-smoke",
            name="Restored office smoke", canvas_type="office_word",
            content=content, status="active",
        ))
        db.flush()
        db.add(CanvasAudit(
            id="audit-smoke", canvas_id="canvas-smoke",
            tenant_id="tenant-smoke", action_type="update",
            user_id="user-smoke", agent_id=None, canvas_type="office_word",
            details_json={"content": content,
                          "operation_id": "synthetic-seed-operation"},
        ))
        db.add(IngestedDocument(
            id="document-smoke", workspace_id="ws-smoke",
            tenant_id="tenant-smoke", file_name=document_file.name,
            file_path=str(document_file), file_type="txt",
            integration_id="upload", external_id="document-smoke",
            file_size_bytes=document_file.stat().st_size,
        ))
        db.add(GoalObjective(
            id="goal-smoke", tenant_id="tenant-smoke",
            workspace_id="ws-smoke", title="Restore smoke goal",
            description="Ordinary fixture for readback only; not business completion.",
            status="active", progress=0.0, criteria=[], key_results=[],
            metadata_json={"seed": "child_restore_smoke",
                           "claim": "readback_fixture_only"},
            owner_id="user-smoke", source="api",
        ))
        db.commit()
    engine.dispose()

    ids = {
        "schema": "atom-child-restore-smoke-ids-1",
        "seeded_via": "product_models_ordinary_fixture",
        "business_completion_claimed": False,
        "source_root": str(source),
        "email": email,
        "user_id": "user-smoke",
        "workspace_id": "ws-smoke",
        "tenant_id": "tenant-smoke",
        "canvas_id": "canvas-smoke",
        "goal_id": "goal-smoke",
        "document_id": "document-smoke",
        "office_artifact_path": str(office_file),
        "office_artifact_sha256": artifact_sha,
        "document_file_path": str(document_file),
        "document_sha256": document_sha,
    }
    Path(args.ids_out).write_text(json.dumps(ids, indent=2) + "\n")
    print(json.dumps(ids, indent=2))


if __name__ == "__main__":
    main()
