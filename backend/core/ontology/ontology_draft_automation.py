"""Consent-gated automation for ontology draft promotion.

Auto-discovered entity types — ``EntityTypeDefinition`` rows created with
``is_active=False`` by schema discovery on integration syncs, OpenIE
discovery, and single-entity linking — are invisible to the active ontology
schema (``OntologyService._load_schema`` filters ``is_active``) until a human
PATCHes ``{"is_active": true}``. Nothing notices them: discovered types rot
as invisible drafts. This module automates that promotion following the
repo's established consent-gated pattern (fleet-router / stage-router /
trust-calibration: ``off|notify|approve|auto``), evidence-thresholded, and
it never overrides a manual decision.

Evidence model (all SQL-computable, deterministic):

* ``usage`` — GraphNodes in the tenant whose type label matches the draft
  (the slug, metadata ``discovered_type``, the display name, or the
  record-type suffix of the hybrid ``{workspace}_{integration}_{type}``
  slug format). This is *live* evidence: nodes exist and use the label.
* ``evolved`` — ``version >= 2``: the idempotent discoverer
  (``resolve_or_create_draft``) has seen the type at least twice with a
  different shape and evolved the schema. Re-discovery is recurrence.
* ``samples`` — discovery metadata ``sample_count`` when present
  (LLM-discovery producers set it; integration-sync discovery does not).
* ``age`` — days since creation. A type created minutes ago is one
  ingestion burst, not a recurring type; never promote too young.

Certification:

* promote when ``(usage >= MIN_NODES OR evolved) AND age >= MIN_AGE_DAYS``
  and ``samples >= MIN_SAMPLES`` when ``sample_count`` is present, and no
  unsuperseded manual decision says otherwise.
* revoke (ALWAYS automatic, any mode) when a previously-applied type has
  zero usage, no schema evolution since promotion, and is at least
  REVOKE_STALE_DAYS old — the evidence that justified the promotion
  evaporated.

Consent modes:

* ``off``     — pass is a no-op; ``census()`` still reports (routes stay
  usable so the operator can flip the mode).
* ``notify``  — record a ``notified`` ledger row + admin notification
  (cooldown-deduped); never activates anything.
* ``approve`` — record an ``approval`` row + notification; the admin
  applies via ``POST /api/v1/ontology-drafts/approve/{action_id}``.
* ``auto``    — eligible drafts activate immediately; the ledger records
  everything for audit.

Never touches manual decisions:

* The PATCH route stamps ``metadata_json["manual_decisions"]`` whenever a
  human passes ``is_active`` explicitly. A retirement (``is_active=False``)
  shelves re-promotion until a newer human decision.
* A human decision newer than the last automation action for the type wins
  outright — the pass skips the type entirely.
* System types (``is_system=True``) are never in scope.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

_mode: Optional[str] = None
_interval_min: Optional[float] = None
_last_pass_monotonic: float = 0.0
_notified_keys: Dict[str, float] = {}
_last_pass_result: Optional[Dict[str, Any]] = None


def _env_str(name: str, default: str) -> str:
    # Env wins > runtime_settings DB row (UI admin) > default.
    from core.runtime_settings import get_setting

    value = get_setting(name, default)
    return value if isinstance(value, str) else default


def _env_int(name: str, default: int) -> int:
    from core.runtime_settings import get_setting

    try:
        return int(get_setting(name, default))
    except (TypeError, ValueError):  # noqa: PERF203
        return default


def _env_float(name: str, default: float) -> float:
    from core.runtime_settings import get_setting

    try:
        return float(get_setting(name, default))
    except (TypeError, ValueError):  # noqa: PERF203
        return default


# ------------------------------------------------------------------ config


def automation_mode() -> str:
    global _mode
    if _mode is not None:
        return _mode
    raw = _env_str("ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE", "off").lower()
    return raw if raw in ("off", "notify", "approve", "auto") else "off"


def automation_interval_min() -> float:
    global _interval_min
    if _interval_min is not None:
        return _interval_min
    try:
        return float(_env_str("ATOM_ONTOLOGY_DRAFT_AUTO_INTERVAL_MIN", "60"))
    except ValueError:  # noqa: PERF203
        return 60.0


def set_automation_config(
    mode: Optional[str] = None, interval_min: Optional[float] = None
) -> Dict[str, Any]:
    global _mode, _interval_min
    if mode is not None:
        if mode not in ("off", "notify", "approve", "auto"):
            raise ValueError(f"invalid mode: {mode}")
        _mode = mode
    if interval_min is not None:
        _interval_min = max(float(interval_min), 1.0)
    return {"mode": automation_mode(), "interval_min": automation_interval_min()}


def thresholds() -> Dict[str, Any]:
    """Evidence thresholds resolution (UI-administrable via runtime settings)."""
    return {
        "min_nodes": _env_int("ATOM_ONTOLOGY_DRAFT_AUTO_MIN_NODES", 3),
        "min_age_days": _env_int("ATOM_ONTOLOGY_DRAFT_AUTO_MIN_AGE_DAYS", 2),
        "min_samples": _env_int("ATOM_ONTOLOGY_DRAFT_AUTO_MIN_SAMPLES", 3),
        "revoke_stale_days": _env_int("ATOM_ONTOLOGY_DRAFT_AUTO_REVOKE_STALE_DAYS", 14),
        "notify_cooldown_hours": _env_float(
            "ATOM_ONTOLOGY_DRAFT_AUTO_NOTIFY_COOLDOWN_HOURS", 24.0
        ),
    }


# ------------------------------------------------------------------ helpers


def _as_utc(dt: Optional[datetime]) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC for age math."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _label_candidates(draft: Any) -> Set[str]:
    """Lowercase label candidates to match against GraphNode.type.

    Covers the three discovery slug shapes in the repo:
    - exact slug (OpenIE discovery, single-entity linking),
    - metadata ``discovered_type`` (LLM discovery),
    - the ``{workspace}_{integration}_{type}`` composite from integration
      sync discovery — suffix after the first two tokens.
    """
    meta = draft.metadata_json or {}
    candidates = {
        str(draft.slug).lower(),
        str(draft.display_name or "").lower(),
    }
    raw = meta.get("discovered_type")
    if raw:
        candidates.add(str(raw).lower())
    tokens = str(draft.slug).split("_")
    if len(tokens) >= 3:
        suffix = "_".join(tokens[2:]).lower()
        if suffix:
            candidates.add(suffix)
    return {c for c in candidates if c}


def _node_type_counts(db, tenant_id: str) -> Dict[str, Tuple[int, int]]:
    """{lowercased type label: (node_count, distinct_workspace_count)}."""
    from sqlalchemy import func

    from core.models import GraphNode

    rows = (
        db.query(
            GraphNode.type,
            func.count(GraphNode.type),
            func.count(func.distinct(GraphNode.workspace_id)),
        )
        .filter(GraphNode.tenant_id == tenant_id)
        .group_by(GraphNode.type)
        .all()
    )
    out: Dict[str, Tuple[int, int]] = {}
    for label, cnt, ws in rows:
        out[str(label).lower()] = (int(cnt), int(ws))
    return out


def collect_evidence(
    db, draft: Any, node_map: Optional[Dict[str, Tuple[int, int]]] = None
) -> Dict[str, Any]:
    """Compute the evidence vector for one draft (pure SQL, never raises)."""
    try:
        from core.models import EntityTypeVersionHistory

        if node_map is None:
            node_map = _node_type_counts(db, draft.tenant_id)
        candidates = _label_candidates(draft)
        matching: Dict[str, Tuple[int, int]] = {}
        for label in candidates:
            if label in node_map:
                matching[label] = node_map[label]
        usage = sum(cnt for cnt, _ in matching.values())
        workspaces = max((ws for _, ws in matching.values()), default=0)
        snapshots = (
            db.query(EntityTypeVersionHistory)
            .filter(EntityTypeVersionHistory.entity_type_id == draft.id)
            .count()
        )
        # Staleness = time since the last SCHEMA change (version snapshot),
        # falling back to creation. The automation's own writes (is_active
        # flip, metadata stamps) fire updated_at and would reset the signal,
        # so updated_at is deliberately not used.
        from sqlalchemy import func

        last_change = (
            db.query(func.max(EntityTypeVersionHistory.created_at))
            .filter(EntityTypeVersionHistory.entity_type_id == draft.id)
            .scalar()
        )
        meta = draft.metadata_json or {}
        age_days = max(
            int((datetime.now(timezone.utc) - _as_utc(draft.created_at)).total_seconds() // 86400),
            0,
        )
        stale_ref = _as_utc(last_change) if last_change else _as_utc(draft.created_at)
        stale_days = max(
            int((datetime.now(timezone.utc) - stale_ref).total_seconds() // 86400), 0
        )
        sample_count = meta.get("sample_count")
        return {
            "node_count": usage,
            "matching_labels": sorted(matching.keys()),
            "workspace_count": workspaces,
            "schema_versions": snapshots,
            "version": draft.version,
            "evolved": int(draft.version or 1) >= 2,
            "sample_count": sample_count,
            "age_days": age_days,
            "stale_days": stale_days,
            "slug": draft.slug,
        }
    except Exception as exc:  # noqa: BLE001 — evidence must never break the pass
        logger.debug(f"evidence collection failed for {draft.slug}: {exc}")
        return {"node_count": 0, "matching_labels": [], "workspace_count": 0,
                "schema_versions": 0, "version": draft.version, "evolved": False,
                "sample_count": None, "age_days": 0, "stale_days": 0,
                "slug": draft.slug}


def promote_verdict(
    evidence: Dict[str, Any], th: Dict[str, Any], base_version: int = 1
) -> Tuple[bool, List[str]]:
    """Evidence certification: (promote?, reasons).

    ``base_version`` is the schema version recorded in the type's latest
    automation action, so the *evolution* signal means "discovered with a
    new shape since the last automation decision" — a type revoked when its
    evidence evaporated cannot ride its stale evolution straight back in.
    """
    reasons: List[str] = []
    new_evolution = evidence["version"] > base_version
    if evidence["age_days"] < th["min_age_days"]:
        reasons.append(
            f"age {evidence['age_days']}d < {th['min_age_days']}d floor"
        )
    if not (evidence["node_count"] >= th["min_nodes"] or new_evolution):
        reasons.append(
            f"no evidence: nodes={evidence['node_count']} (<{th['min_nodes']}) "
            f"and no new evolution since last decision"
        )
    sc = evidence.get("sample_count")
    if sc is not None and int(sc) < th["min_samples"]:
        reasons.append(f"samples {sc} < {th['min_samples']}")
    return (not reasons, reasons)


def revoke_verdict(
    evidence: Dict[str, Any], th: Dict[str, Any], base_version: int = 1
) -> Tuple[bool, List[str]]:
    """Revocation certification: zero usage, no new evolution, stale.

    ``base_version`` is the schema version the type was promoted at.
    """
    reasons: List[str] = []
    if evidence["node_count"] > 0:
        reasons.append(f"still used by {evidence['node_count']} nodes")
    if evidence["version"] > base_version:
        reasons.append("schema evolved since promotion")
    if evidence["stale_days"] < th["revoke_stale_days"]:
        reasons.append(
            f"staleness {evidence['stale_days']}d < {th['revoke_stale_days']}d"
        )
    return (not reasons, reasons)


def _base_version(latest: Optional[Dict[str, Any]]) -> int:
    """Schema version recorded in the latest automation action (default 1)."""
    if not latest:
        return 1
    ev = latest.get("evidence") or {}
    try:
        return int(ev.get("version") or 1)
    except (TypeError, ValueError):  # noqa: PERF203
        return 1


# ------------------------------------------------------------------ ledger


def _record_action(
    db, tenant_id: str, entity_type_id: str, slug: str,
    verdict: str, state: str, evidence: Dict[str, Any],
) -> int:
    from core.models import OntologyDraftAction

    row = OntologyDraftAction(
        tenant_id=tenant_id,
        entity_type_id=entity_type_id,
        slug=slug,
        verdict=verdict,
        mode=automation_mode(),
        state=state,
        evidence_json=evidence,
        decided_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    return int(row.id)


def _latest_action_for_type(db, tenant_id: str, entity_type_id: str) -> Optional[Dict[str, Any]]:
    from core.models import OntologyDraftAction

    row = (
        db.query(OntologyDraftAction)
        .filter(
            OntologyDraftAction.tenant_id == tenant_id,
            OntologyDraftAction.entity_type_id == entity_type_id,
        )
        .order_by(OntologyDraftAction.created_at.desc(), OntologyDraftAction.id.desc())
        .first()
    )
    if not row:
        return None
    return {
        "id": row.id,
        "verdict": row.verdict,
        "state": row.state,
        "created_at": _as_utc(row.created_at),
        "evidence": dict(row.evidence_json or {}),
    }


# ------------------------------------------------------- manual-decision guard


def manual_decision_respects(draft: Any, latest_auto: Optional[Dict[str, Any]]) -> bool:
    """True when automation may act on the type.

    A human decision recorded via the PATCH route (metadata
    ``manual_decisions``, oldest→newest) wins unless the automation's last
    action for the type is NEWER than it (the human choice was superseded
    by the system, e.g. retire-then-recover).
    """
    meta = draft.metadata_json or {}
    manual = meta.get("manual_decisions") or []
    if not manual:
        return True
    last = manual[-1]
    try:
        last_at = datetime.fromisoformat(str(last.get("at", "")))
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
    except ValueError:  # noqa: PERF203
        return True  # malformed entry — don't block on it
    if latest_auto and _as_utc(latest_auto["created_at"]) > last_at:
        return True
    return False


def _apply_promotion(db, entity_type_id: str, tenant_id: str, action_id: int) -> bool:
    """Flip is_active=True + stamp the automation history on the metadata."""
    from core.models import EntityTypeDefinition

    entity = (
        db.query(EntityTypeDefinition)
        .filter(EntityTypeDefinition.id == entity_type_id,
                EntityTypeDefinition.tenant_id == tenant_id)
        .first()
    )
    if not entity or entity.is_system:
        return False
    entity.is_active = True
    meta = dict(entity.metadata_json or {})
    auto = dict(meta.get("automation") or {})
    auto["promoted_at"] = datetime.now(timezone.utc).isoformat()
    auto["promoted_by_action_id"] = action_id
    meta["automation"] = auto
    entity.metadata_json = meta
    db.commit()
    logger.info("Ontology draft promoted: %s/%s (action %s)", tenant_id, entity.slug, action_id)
    return True


def _apply_revoke(db, entity_type_id: str, tenant_id: str, action_id: int) -> bool:
    from core.models import EntityTypeDefinition

    entity = (
        db.query(EntityTypeDefinition)
        .filter(EntityTypeDefinition.id == entity_type_id,
                EntityTypeDefinition.tenant_id == tenant_id)
        .first()
    )
    if not entity or entity.is_system:
        return False
    entity.is_active = False
    meta = dict(entity.metadata_json or {})
    auto = dict(meta.get("automation") or {})
    auto["revoked_at"] = datetime.now(timezone.utc).isoformat()
    auto["revoked_by_action_id"] = action_id
    meta["automation"] = auto
    entity.metadata_json = meta
    db.commit()
    logger.info("Ontology draft promotion REVOKED: %s/%s (action %s)",
                tenant_id, entity.slug, action_id)
    return True


def approve_action(db, action_id: str) -> bool:
    """Admin consent: a queued approval becomes applied (activates the type)."""
    from core.models import OntologyDraftAction

    row = db.query(OntologyDraftAction).filter_by(id=action_id).first()
    if not row or row.state != "approval":
        return False
    if row.verdict != "promote":
        row.state = "rejected"
        db.commit()
        return False
    row.state = "applied"
    row.decided_at = datetime.now(timezone.utc)
    db.commit()
    applied = _apply_promotion(db, row.entity_type_id, row.tenant_id, int(row.id))
    logger.info("Ontology draft action %s approved -> applied (promoted=%s)",
                action_id, applied)
    return True


def reject_action(db, action_id: str) -> bool:
    from core.models import OntologyDraftAction

    row = db.query(OntologyDraftAction).filter_by(id=action_id).first()
    if not row or row.state != "approval":
        return False
    row.state = "rejected"
    row.decided_at = datetime.now(timezone.utc)
    db.commit()
    return True


# -------------------------------------------------------------- notifications


def _notify(title: str, message: str) -> None:
    try:
        import asyncio

        from core.notification_service import NotificationService

        svc = NotificationService(db_session=None)
        recipient = _admin_recipient()
        if not recipient:
            return
        coro = svc.send_notification(
            user_id=recipient, notification_type="ontology_draft_update",
            data={"title": title, "message": message},
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            asyncio.run(coro)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"ontology draft notify skipped: {exc}")


def _admin_recipient() -> Optional[str]:
    try:
        from core.database import SessionLocal
        from core.models import User, UserRole

        with SessionLocal() as db:
            u = db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).first()
            return u.id if u else None
    except Exception:  # noqa: BLE001
        return None


def _notify_cooldown_active(key: str, hours: float = 24.0) -> bool:
    last = _notified_keys.get(key, 0.0)
    return (time.monotonic() - last) < hours * 3600


# ------------------------------------------------------------------ the pass


def _tenants_with_drafts(db, tenant_id: Optional[str]) -> List[str]:
    from core.models import EntityTypeDefinition

    q = (
        db.query(EntityTypeDefinition.tenant_id)
        .filter(EntityTypeDefinition.is_active.is_(False),
                EntityTypeDefinition.is_system.is_(False))
        .distinct()
    )
    if tenant_id:
        q = q.filter(EntityTypeDefinition.tenant_id == tenant_id)
    return [row[0] for row in q.all()]


def _tenants_with_applied(db, tenant_id: Optional[str]) -> List[str]:
    """Tenants owning at least one promotion the automation applied —
    revocation candidates live there even when no draft remains inactive."""
    from core.models import OntologyDraftAction

    q = (
        db.query(OntologyDraftAction.tenant_id)
        .filter(OntologyDraftAction.verdict == "promote",
                OntologyDraftAction.state == "applied")
        .distinct()
    )
    if tenant_id:
        q = q.filter(OntologyDraftAction.tenant_id == tenant_id)
    return [row[0] for row in q.all()]


def _drafts_for(db, tenant_id: str) -> List[Any]:
    from core.models import EntityTypeDefinition

    return (
        db.query(EntityTypeDefinition)
        .filter(EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.is_active.is_(False),
                EntityTypeDefinition.is_system.is_(False))
        .all()
    )


def _applied_types_for(db, tenant_id: str) -> List[Tuple[int, Any]]:
    """(action_id, entity) pairs whose latest automation decision is applied,
    i.e. revocation candidates."""
    from core.models import EntityTypeDefinition, OntologyDraftAction

    rows = (
        db.query(OntologyDraftAction)
        .filter(OntologyDraftAction.tenant_id == tenant_id,
                OntologyDraftAction.verdict == "promote",
                OntologyDraftAction.state == "applied")
        .all()
    )
    out: List[Tuple[int, Any]] = []
    for r in rows:
        latest = _latest_action_for_type(db, tenant_id, r.entity_type_id)
        if not latest or latest["id"] != r.id or latest["state"] != "applied":
            continue  # superseded (revoked/rejected/newer queue) — not a candidate
        entity = (
            db.query(EntityTypeDefinition)
            .filter(EntityTypeDefinition.id == r.entity_type_id,
                    EntityTypeDefinition.tenant_id == tenant_id)
            .first()
        )
        if entity is None or entity.is_system or not entity.is_active:
            continue
        out.append((int(r.id), entity))
    return out


def run_automation_pass(db, tenant_id: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    """One evidence+consent pass over every discovered draft. Never raises."""
    global _last_pass_monotonic, _last_pass_result

    mode = automation_mode()
    if mode == "off":
        result = {"ran": False, "why": "disabled"}
        _last_pass_result = result
        return result

    interval = automation_interval_min()
    if (
        not force
        and mode != "auto"
        and (time.monotonic() - _last_pass_monotonic) < interval * 60
    ):
        result = {"ran": False, "why": "interval"}
        _last_pass_result = result
        return result

    _last_pass_monotonic = time.monotonic()
    th = thresholds()
    summary: Dict[str, Any] = {
        "ran": True, "mode": mode, "tenants_scanned": 0,
        "drafts_scanned": 0, "promoted": [], "queued": [], "notified": [],
        "revoked": [], "held": [], "manual_held": [], "errors": [],
    }

    try:
        tenants = sorted(
            set(_tenants_with_drafts(db, tenant_id))
            | set(_tenants_with_applied(db, tenant_id))
        )
        for tid in tenants:
            summary["tenants_scanned"] += 1
            node_map = _node_type_counts(db, tid)
            # Revocation first: pre-existing applied promotions whose
            # evidence evaporated. Always automatic, regardless of mode —
            # but never overrides an unsuperseded manual decision.
            for action_id, entity in _applied_types_for(db, tid):
                latest = _latest_action_for_type(db, tid, entity.id)
                if not manual_decision_respects(entity, latest):
                    summary["manual_held"].append(entity.slug)
                    continue
                evidence = collect_evidence(db, entity, node_map)
                base_version = _base_version(latest)
                ok, reasons = revoke_verdict(evidence, th, base_version)
                if ok:
                    rid = _record_action(db, tid, entity.id, entity.slug,
                                         "revoke", "revoked", evidence)
                    _apply_revoke(db, entity.id, tid, rid)
                    summary["revoked"].append(
                        {"slug": entity.slug, "action_id": rid, "evidence": evidence})
                else:
                    summary["held"].append(
                        {"slug": entity.slug, "reasons": ["revoke: " + "; ".join(reasons)]})
            for draft in _drafts_for(db, tid):
                summary["drafts_scanned"] += 1
                latest = _latest_action_for_type(db, tid, draft.id)
                if not manual_decision_respects(draft, latest):
                    summary["manual_held"].append(draft.slug)
                    continue
                evidence = collect_evidence(db, draft, node_map)
                base_version = _base_version(latest)
                ok, reasons = promote_verdict(evidence, th, base_version)
                if not ok:
                    summary["held"].append({"slug": draft.slug, "reasons": reasons})
                    continue
                # Previously applied + still inactive => someone retired it
                # (automation revokes flip the ledger, so an applied row here
                # with an inactive entity is a human retirement handled by the
                # manual guard above).
                key = f"promote:{tid}:{draft.id}"
                if mode == "auto":
                    aid = _record_action(db, tid, draft.id, draft.slug,
                                         "promote", "applied", evidence)
                    _apply_promotion(db, draft.id, tid, aid)
                    summary["promoted"].append(
                        {"slug": draft.slug, "action_id": aid, "evidence": evidence})
                elif mode == "approve":
                    aid = _record_action(db, tid, draft.id, draft.slug,
                                         "promote", "approval", evidence)
                    _notify(f"Ontology draft certified: {draft.slug}",
                            f"Evidence passed — approve via "
                            f"/api/v1/ontology-drafts/approve/{aid}.")
                    summary["queued"].append(
                        {"slug": draft.slug, "action_id": aid, "evidence": evidence})
                else:  # notify
                    if not _notify_cooldown_active(key, th["notify_cooldown_hours"]):
                        aid = _record_action(db, tid, draft.id, draft.slug,
                                             "promote", "notified", evidence)
                        _notify(f"Ontology draft certified: {draft.slug}",
                                "Evidence passed — promote via PATCH is_active.")
                        _notified_keys[key] = time.monotonic()
                        summary["notified"].append(
                            {"slug": draft.slug, "action_id": aid})
                    else:
                        summary["held"].append(
                            {"slug": draft.slug, "reasons": ["notify cooldown"]})
    except Exception as exc:  # noqa: BLE001 — pass never raises
        summary["errors"].append(f"{type(exc).__name__}")
        logger.warning(f"ontology draft automation pass failed: {exc}")

    _last_pass_result = summary
    return summary


def census(db, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Read-only draft census + automation state (never mutates)."""
    from core.models import EntityTypeDefinition, OntologyDraftAction

    try:
        drafts = _drafts_for(db, tenant_id) if tenant_id else [
            d for tid in _tenants_with_drafts(db, None) for d in _drafts_for(db, tid)
        ]
    except Exception:  # noqa: BLE001
        drafts = []
    th = thresholds()
    eligible: List[str] = []
    for draft in drafts:
        latest = _latest_action_for_type(db, draft.tenant_id, draft.id)
        if not manual_decision_respects(draft, latest):
            continue
        evidence = collect_evidence(db, draft)
        ok, _ = promote_verdict(evidence, th, _base_version(latest))
        if ok:
            eligible.append(draft.slug)
    q = db.query(OntologyDraftAction)
    if tenant_id:
        q = q.filter(OntologyDraftAction.tenant_id == tenant_id)
    states = {
        s: q.filter(OntologyDraftAction.state == s).count()
        for s in ("approval", "applied", "rejected", "revoked", "notified")
    }
    return {
        "mode": automation_mode(),
        "interval_min": automation_interval_min(),
        "thresholds": th,
        "drafts_total": len(drafts),
        "drafts_eligible": len(eligible),
        "eligible_slugs": eligible,
        "ledger": states,
        "last_pass": _last_pass_result,
    }


def list_pending(db, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Queued approvals awaiting admin consent."""
    from core.models import OntologyDraftAction

    q = (
        db.query(OntologyDraftAction)
        .filter(OntologyDraftAction.state == "approval",
                OntologyDraftAction.verdict == "promote")
        .order_by(OntologyDraftAction.created_at.asc())
    )
    if tenant_id:
        q = q.filter(OntologyDraftAction.tenant_id == tenant_id)
    return [
        {
            "id": r.id, "tenant_id": r.tenant_id, "entity_type_id": r.entity_type_id,
            "slug": r.slug, "mode": r.mode, "evidence": r.evidence_json,
            "created_at": _as_utc(r.created_at).isoformat(),
        }
        for r in q.limit(200).all()
    ]
