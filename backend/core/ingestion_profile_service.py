"""Ingestion Profile Service — org-sharing of ingestion *configuration*.

Org Ingestion Sharing Phase 1
(docs/architecture/ORG_INGESTION_SHARING_PLAN.md): an org admin configures
ingestion sources once, exports a signed JSON profile, and members import it.
The profile describes **how** to ingest (integrations, entity types,
frequencies, folder rules) — never credentials and never data.

Security invariants:
- Export runs the payload through ``strip_credentials`` (P5) and FAILS CLOSED
  (raises) if any credential-shaped key survives.
- Profiles are Ed25519-signed by the exporter (``core/org_sharing_crypto``)
  and verified BEFORE the payload is applied on import.
- Import only touches integrations the profile lists; a member's personal
  sources are never modified.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.blueprint_sanitizer import has_credentials, strip_credentials

logger = logging.getLogger(__name__)

PROFILE_VERSION = 1
PROFILE_KIND = "atom_ingestion_profile"


def canonical_payload(payload: Dict[str, Any]) -> bytes:
    """Canonical JSON encoding used for hashing + signing (sorted, compact)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(payload)).hexdigest()


class IngestionProfileError(ValueError):
    """Raised for structurally invalid/unsafe profiles (never swallowed)."""


class IngestionProfileService:
    """Build/apply signed ingestion profiles for org sharing."""

    def build_profile(self, db: Session, workspace_id: str) -> Dict[str, Any]:
        """Assemble the unsigned profile payload from persisted ingestion settings."""
        from core.models import IngestionSettings

        rows = db.query(IngestionSettings).filter(
            IngestionSettings.workspace_id == workspace_id
        ).all()

        integrations: List[Dict[str, Any]] = []
        for row in rows:
            entry: Dict[str, Any] = {
                "integration_id": row.integration_id,
                "enabled": bool(row.enabled),
                "sync_frequency_minutes": row.sync_frequency_minutes,
                # document-ingestion settings (folder rules etc.)
                "auto_sync_new_files": row.auto_sync_new_files,
                "file_types": row.file_types or [],
                "sync_folders": row.sync_folders or [],
                "exclude_folders": row.exclude_folders or [],
                "max_file_size_mb": row.max_file_size_mb,
            }
            # hybrid-pipeline settings (Phase 0 columns; absent/empty on
            # document-ingestion-only rows)
            if row.entity_types:
                entry["entity_types"] = list(row.entity_types or [])
                entry["sync_last_n_days"] = row.sync_last_n_days
                entry["max_records_per_sync"] = row.max_records_per_sync
                entry["sync_mode"] = row.sync_mode
            integrations.append(entry)

        profile = {
            "kind": PROFILE_KIND,
            "profile_version": PROFILE_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "workspace_id": workspace_id,
            "integrations": integrations,
        }

        # P5: sharing never leaks credentials. strip + fail closed.
        cleaned = strip_credentials(profile)
        if has_credentials(cleaned):
            raise IngestionProfileError(
                "Refusing to export ingestion profile: credential-shaped keys survived sanitization"
            )
        return cleaned

    def export_profile(self, db: Session, workspace_id: str) -> Dict[str, Any]:
        """Build + sign the shareable profile envelope."""
        from core import org_sharing_crypto

        payload = self.build_profile(db, workspace_id)
        signature, signed_by = org_sharing_crypto.sign_payload(canonical_payload(payload))
        return {
            "kind": PROFILE_KIND,
            "payload": payload,
            "payload_hash": payload_hash(payload),
            "signature": signature,
            "signed_by": signed_by,
        }

    def apply_profile(
        self,
        db: Session,
        envelope: Dict[str, Any],
        workspace_id: str,
        tenant_id: Optional[str] = None,
        performed_by: Optional[str] = None,
        require_signature: bool = True,
    ) -> Dict[str, Any]:
        """Verify + apply an exported profile envelope to this instance.

        Returns a summary dict (applied integrations, counts). Raises
        ``IngestionProfileError`` on invalid structure or a failed signature.
        """
        from core import org_sharing_crypto
        from core.models import IngestionSettings, IngestionProfileImport

        if not isinstance(envelope, dict) or envelope.get("kind") != PROFILE_KIND:
            raise IngestionProfileError("Not an Atom ingestion profile (bad kind)")
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise IngestionProfileError("Profile envelope has no payload")
        version = payload.get("profile_version")
        if version != PROFILE_VERSION:
            raise IngestionProfileError(f"Unsupported profile_version {version!r}")

        # Verify BEFORE applying. Rejected profiles are ALWAYS audited (plan
        # §6: "unverified bundles are rejected and audited") — the audit row
        # records signature_valid=False for later review.
        signature_valid = False
        try:
            if require_signature:
                signature = envelope.get("signature")
                if not signature:
                    raise IngestionProfileError("Profile is not signed")
                if payload_hash(payload) != envelope.get("payload_hash", ""):
                    raise IngestionProfileError("Payload hash mismatch — profile was tampered with")
                signature_valid = org_sharing_crypto.verify_payload(
                    db, canonical_payload(payload), str(signature), workspace_id
                )
                if not signature_valid:
                    raise IngestionProfileError(
                        "Profile signature verification failed (signer not in org key registry)"
                    )
        except IngestionProfileError:
            db.add(IngestionProfileImport(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                profile_version=PROFILE_VERSION,
                signature_valid=False,
                applied_integrations=[],
                performed_by=performed_by,
            ))
            db.commit()
            raise

        # Defense in depth: even verified profiles are sanitized before apply.
        payload = strip_credentials(payload)
        integrations = payload.get("integrations", [])
        if not isinstance(integrations, list):
            raise IngestionProfileError("Profile integrations must be a list")

        applied: List[str] = []
        for entry in integrations:
            integration_id = entry.get("integration_id")
            if not integration_id or not isinstance(integration_id, str):
                continue
            row = db.query(IngestionSettings).filter(
                IngestionSettings.workspace_id == workspace_id,
                IngestionSettings.integration_id == integration_id,
            ).first()
            if row is None:
                row = IngestionSettings(
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    integration_id=integration_id,
                )
                db.add(row)

            row.enabled = bool(entry.get("enabled", False))
            if "sync_frequency_minutes" in entry:
                row.sync_frequency_minutes = int(entry["sync_frequency_minutes"] or 60)
            row.auto_sync_new_files = bool(entry.get("auto_sync_new_files", True))
            if "file_types" in entry:
                row.file_types = list(entry.get("file_types") or [])
            if "sync_folders" in entry:
                row.sync_folders = list(entry.get("sync_folders") or [])
            if "exclude_folders" in entry:
                row.exclude_folders = list(entry.get("exclude_folders") or [])
            if "max_file_size_mb" in entry:
                row.max_file_size_mb = int(entry["max_file_size_mb"] or 50)
            if "entity_types" in entry:
                row.entity_types = list(entry.get("entity_types") or [])
            if "sync_last_n_days" in entry:
                row.sync_last_n_days = int(entry["sync_last_n_days"] or 30)
            if "max_records_per_sync" in entry:
                row.max_records_per_sync = int(entry["max_records_per_sync"] or 1000)
            if "sync_mode" in entry:
                row.sync_mode = str(entry["sync_mode"])
            applied.append(integration_id)

        db.commit()

        # Push hybrid-pipeline configs into the live service so they take
        # effect without a restart.
        live_loaded = 0
        try:
            from core.hybrid_data_ingestion import (
                SyncConfiguration,
                get_hybrid_ingestion_service,
            )
            service = get_hybrid_ingestion_service(workspace_id, tenant_id or "default")
            for entry in integrations:
                integration_id = entry.get("integration_id")
                if not integration_id or entry.get("entity_types") is None:
                    continue
                if not entry.get("enabled"):
                    continue
                service.enable_auto_sync(integration_id, config=SyncConfiguration(
                    integration_id=integration_id,
                    entity_types=list(entry.get("entity_types") or []),
                    sync_last_n_days=int(entry.get("sync_last_n_days") or 30),
                    max_records_per_sync=int(entry.get("max_records_per_sync") or 1000),
                    sync_mode=str(entry.get("sync_mode") or "incremental"),
                ))
                live_loaded += 1
        except Exception as e:  # live reload is best-effort; DB rows are source of truth
            logger.warning(f"Could not hot-reload imported profile into live service: {e}")

        db.add(IngestionProfileImport(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            profile_version=PROFILE_VERSION,
            signature_valid=signature_valid,
            applied_integrations=applied,
            performed_by=performed_by,
        ))
        db.commit()

        return {
            "applied_integrations": applied,
            "count": len(applied),
            "signature_valid": signature_valid,
            "live_reload_count": live_loaded,
        }
