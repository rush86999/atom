"""Authorized-source fixtures for executor and route tests.

The runtime re-checks an applied read's typed binding, authenticated reader
and current bytes before dependent work may consume the cached result. A
pre-applied step with ``inputs={}`` therefore is not an accepted source: it
is an unbound synthetic row. These helpers build the same controlled-fixture
authority the production resolver produces (``resolve_assignment_source``
under ``ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS``): a real file under the
configured fixture root, an active principal in the isolated test database,
and a typed binding whose accepted revision is the file digest.

They deliberately do not create a bypass: the executor still re-resolves the
binding and re-reads the file. Tests that only compile a patch may still use
plain result dicts, because no consumption happens there.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import User


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SourceAuthority:
    """Write controlled fixture files and bind applied reads to them."""

    def __init__(
        self,
        root: Path,
        *,
        user_id: str,
        workspace_id: str,
        tenant_id: str,
    ) -> None:
        self.root = Path(root).resolve()
        self.user_id = str(user_id)
        self.workspace_id = str(workspace_id)
        self.tenant_id = str(tenant_id)

    def _binding(
        self, path: Path, *,
        resource_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        digest = _sha256_file(path)
        return {
            "resource_id": str(resource_id or f"fixture:{path.name}"),
            "dataset_name": None,
            "source": "controlled_fixture",
            "source_kind": "file",
            "external_id": path.name,
            "original_file_name": path.name,
            "representation": "file",
            "source_version": digest,
            "sheet": None,
            "columns": [],
            "numeric_columns": [],
            "row_count": None,
            "coverage": {
                "known": True,
                "truncated": False,
                "controlled_fixture": True,
            },
            "access_scope": {
                "user_id": self.user_id,
                "workspace_id": self.workspace_id,
                "tenant_id": self.tenant_id,
            },
            "workspace_id": self.workspace_id,
            "tenant_id": self.tenant_id,
            "internal_fixture": True,
        }

    def source(
        self, name: str, payload: Any,
        *,
        resource_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """Create one real fixture file and its typed controlled binding."""
        path = (self.root / name).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True))
        return self._binding(path, resource_id=resource_id), str(path)

    def bind_path(
        self, step: Dict[str, Any], path: Any,
        *,
        resource_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Bind a read step to an existing real file it will actually read."""
        path = Path(path).resolve()
        binding = self._binding(path, resource_id=resource_id)
        inputs = dict(step.get("inputs") or {})
        inputs["resource_binding"] = binding
        inputs["path"] = str(path)
        step["inputs"] = inputs
        return step

    def bind(self, step: Dict[str, Any], name: str) -> Dict[str, Any]:
        """Bind a pre-applied read to a real file holding its accepted result.

        The payload is the durable result the compiler later consumes, so the
        fixture models one accepted read rather than a fabricated row list.
        The receipt's version is then the authoritative file revision, exactly
        as a real read adapter records the binding it resolved.
        """
        result = step.get("result") if isinstance(
            step.get("result"), dict) else {}
        binding, path = self.source(
            name, result, resource_id=result.get("resource_id"))
        result["source_version"] = binding["source_version"]
        verification = result.get("verification")
        if isinstance(verification, dict) and "version" in verification:
            verification["version"] = binding["source_version"]
        inputs = dict(step.get("inputs") or {})
        inputs["resource_binding"] = binding
        inputs["path"] = path
        step["inputs"] = inputs
        return step


def install_source_authority(
    monkeypatch,
    root: Path,
    *,
    user_id: str,
    workspace_id: str,
    tenant_id: str,
) -> SourceAuthority:
    """Create the isolated reader DB the runtime re-grant check consults.

    ``get_db_session`` is patched only for the requesting test. The scratch
    database lives under ``root`` and never points at a development database.
    """
    root = Path(root).resolve()
    engine = create_engine(f"sqlite:///{root / 'source_authority.db'}")
    Base.metadata.create_all(engine, checkfirst=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add(User(
            id=str(user_id),
            email=f"{user_id}@example.invalid",
            hashed_password="x",
            first_name="Source",
            last_name="Reader",
            role="member",
            status="active",
            workspace_id=str(workspace_id),
            tenant_id=str(tenant_id),
            is_active=True,
        ))
        db.commit()
    monkeypatch.setattr("core.database.get_db_session", factory)
    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv("ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(root))
    return SourceAuthority(
        root,
        user_id=user_id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
    )


def bind_applied_read(
    step: Dict[str, Any],
    authority: SourceAuthority,
    name: str,
) -> Dict[str, Any]:
    """Convenience wrapper for the common one-read binding."""
    return authority.bind(step, name)
