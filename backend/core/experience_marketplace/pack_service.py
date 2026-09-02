"""Experience Marketplace pack service — export/import/cursor/reputation.

Turns post-run agent memory (episodes, canvas summaries, business facts, graph
ontology, skills) into signed, sanitized lesson packs another instance can
apply — without leaking entity identity, credentials, PII, or sensitive rows.

See docs/architecture/EXPERIENCE_MARKETPLACE.md. Flag:
``ATOM_EXPERIENCE_MARKETPLACE_ENABLED`` (default off).
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.models import (
    AgentEpisode,
    AgentReasoningStep,
    AgentRegistry,
    EpisodeSegment,
    ExperienceExport,
    ExperienceImport,
    ExperienceItem,
    GraphEdge,
    GraphNode,
    IngestionSettings,
    Skill,
)

logger = logging.getLogger(__name__)

PACK_KIND = "atom_experience_pack"
PACK_VERSION = 1


def _model_provenance(agent: Any) -> str:
    """The exporting agent's model, best-effort — WikiSkill W6 ships this so
    the receiving installation can apply the negative-transfer guard
    (weak-model skills can degrade a stronger model catastrophically)."""
    cfg = getattr(agent, "configuration", None)
    if isinstance(cfg, dict):
        for key in ("model", "llm_model", "default_model"):
            val = cfg.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()[:255]
        llm = cfg.get("llm")
        if isinstance(llm, dict):
            val = llm.get("model")
            if isinstance(val, str) and val.strip():
                return val.strip()[:255]
    meta = getattr(agent, "meta_data", None)
    if isinstance(meta, dict):
        val = meta.get("model")
        if isinstance(val, str) and val.strip():
            return val.strip()[:255]
    return "unknown"

SENSITIVITY_LADDER = ["public", "internal", "confidential", "restricted"]
PACK_SECTIONS = ("patterns", "canvas_lessons", "facts", "ontology", "skills")
ITEM_KINDS = ("pattern", "canvas_lesson", "fact", "skill")

MAX_PATTERNS = int(os.getenv("ATOM_EXPERIENCE_PACK_MAX_PATTERNS", "1000"))
MAX_CANVAS_LESSONS = int(os.getenv("ATOM_EXPERIENCE_PACK_MAX_CANVAS_LESSONS", "1000"))
MAX_FACTS = int(os.getenv("ATOM_EXPERIENCE_PACK_MAX_FACTS", "2000"))
MAX_SKILLS = int(os.getenv("ATOM_EXPERIENCE_PACK_MAX_SKILLS", "100"))
MAX_NODES = int(os.getenv("ATOM_EXPERIENCE_PACK_MAX_NODES", "20000"))
MAX_EDGES = int(os.getenv("ATOM_EXPERIENCE_PACK_MAX_EDGES", "50000"))

CURSOR_INTEGRATION = "experience"


class PackError(ValueError):
    """Business error — surface as a generic 4xx, never str(e)."""


def experience_marketplace_enabled() -> bool:
    return os.getenv("ATOM_EXPERIENCE_MARKETPLACE_ENABLED", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Cursor (ingestion_settings.usage_stats_json["experience_cursor"])
# ---------------------------------------------------------------------------
def _read_cursor(db: Session, workspace_id: str) -> Dict[str, Any]:
    row = db.query(IngestionSettings).filter(
        IngestionSettings.integration_id == CURSOR_INTEGRATION,
        IngestionSettings.workspace_id == workspace_id,
    ).first()
    if row is None or not isinstance(row.usage_stats_json, dict):
        return {}
    cursor = row.usage_stats_json.get("experience_cursor")
    return cursor if isinstance(cursor, dict) else {}


def _store_cursor(db: Session, workspace_id: str, cursor: Dict[str, Any]) -> None:
    try:
        row = db.query(IngestionSettings).filter(
            IngestionSettings.integration_id == CURSOR_INTEGRATION,
            IngestionSettings.workspace_id == workspace_id,
        ).first()
        if row is None:
            row = IngestionSettings(
                integration_id=CURSOR_INTEGRATION, workspace_id=workspace_id,
            )
            db.add(row)
        stats = dict(row.usage_stats_json or {})
        stats["experience_cursor"] = cursor
        row.usage_stats_json = stats
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("experience cursor persist failed (non-fatal)")


def _iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).isoformat()
    return str(dt)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iter_items(sec: Any) -> Iterable[Dict]:
    if isinstance(sec, dict):
        for sub in sec.values():
            yield from _iter_items(sub)
    elif isinstance(sec, list):
        for i in sec:
            if isinstance(i, dict):
                yield i


def _collect_texts(section_items: Dict[str, Any], registry_names: List[str]) -> Iterable[str]:
    """All exported string values, for the post-assembly leak scan."""
    from core.experience_marketplace.sanitizer import tuple_texts

    texts = list(tuple_texts(section_items))
    texts.append(" ".join(registry_names))  # tokens themselves are safe by construction
    return [t for t in texts if isinstance(t, str)]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
class ExperiencePackService:
    """Export / import / reputation for experience packs."""

    def _allowed(self, ceiling: str) -> set:
        if ceiling not in SENSITIVITY_LADDER:
            raise PackError("Invalid sensitivity_ceiling")
        return set(SENSITIVITY_LADDER[: SENSITIVITY_LADDER.index(ceiling) + 1])

    # -- patterns -----------------------------------------------------------
    def _export_patterns(self, db, workspace_id, agent_id, since_ts, allowed, registry):
        from core.experience_marketplace.sanitizer import bucket_value, guess_kind, sanitize_text

        q = db.query(AgentEpisode).filter(
            AgentEpisode.workspace_id == workspace_id,
            AgentEpisode.agent_id == agent_id,
        )
        if since_ts:
            q = q.filter(AgentEpisode.updated_at > since_ts)
        episodes = q.order_by(AgentEpisode.updated_at.desc()).limit(MAX_PATTERNS).all()
        if not episodes:
            return [], {}

        # Verified-step counts (graduation gate semantics — only 'verified').
        execution_ids = [e.execution_id for e in episodes if e.execution_id]
        verified_counts: Dict[str, int] = {}
        if execution_ids:
            try:
                rows = (
                    db.query(AgentReasoningStep.execution_id, func.count())
                    .filter(AgentReasoningStep.execution_id.in_(execution_ids))
                    .filter(AgentReasoningStep.verified == "verified")
                    .group_by(AgentReasoningStep.execution_id)
                    .all()
                )
                verified_counts = {rid: n for rid, n in rows}
            except Exception:
                verified_counts = {}

        items: List[Dict] = []
        excluded: Dict[str, int] = {}
        for ep in episodes:
            meta = ep.metadata_json or {}
            sensitivity = meta.get("sensitivity", "internal")
            if sensitivity not in allowed:
                excluded[sensitivity] = excluded.get(sensitivity, 0) + 1
                continue
            conditions = {}
            for k, v in (meta or {}).items():
                if k in ("sensitivity",):
                    continue
                conditions[k] = bucket_value(v, guess_kind(k))
            outcome = ep.outcome or ("success" if ep.success else "failure")
            lesson = sanitize_text(ep.task_description or "", registry)
            payload = {
                "task_class": (ep.topics or [None])[0] if isinstance(ep.topics, list) else None,
                "lesson": f"{lesson[:500]} -> outcome: {outcome}",
                "outcome": outcome,
                "conditions": conditions,
                "verified_step_count": verified_counts.get(ep.execution_id, 0),
                "supervisor_rating": ep.supervisor_rating,
                "aggregate_feedback_score": ep.aggregate_feedback_score,
                "step_efficiency": ep.step_efficiency,
                "confidence": ep.confidence_score,
                "maturity_at_time": ep.maturity_at_time
                if isinstance(ep.maturity_at_time, str) else None,
            }
            items.append({
                "item_id": f"ep:{ep.id}",
                "kind": "pattern",
                "sensitivity": sensitivity,
                "updated_at": _iso(ep.updated_at or ep.created_at),
                "payload": payload,
            })
        return items, excluded

    # -- canvas lessons ------------------------------------------------------
    def _export_canvas_lessons(self, db, workspace_id, agent_id, since_ts, allowed, registry):
        from core.experience_marketplace.sanitizer import bucket_value, guess_kind, sanitize_text

        q = (
            db.query(EpisodeSegment, AgentEpisode)
            .join(AgentEpisode, EpisodeSegment.episode_id == AgentEpisode.id)
            .filter(AgentEpisode.workspace_id == workspace_id)
            .filter(AgentEpisode.agent_id == agent_id)
            .filter(EpisodeSegment.canvas_context.isnot(None))
        )
        if since_ts:
            q = q.filter(EpisodeSegment.created_at > since_ts)
        rows = q.order_by(EpisodeSegment.created_at.desc()).limit(MAX_CANVAS_LESSONS * 4).all()

        items: List[Dict] = []
        excluded: Dict[str, int] = {}
        seen: set = set()
        for segment, episode in rows:
            ctx = segment.canvas_context or {}
            if not ctx.get("presentation_summary"):
                continue
            canvas_type = ctx.get("canvas_type") or "generic"
            summary = str(ctx["presentation_summary"])
            dedupe_key = (canvas_type, hashlib.sha256(summary.encode()).hexdigest()[:16])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            sensitivity = (episode.metadata_json or {}).get("sensitivity", "internal")
            if sensitivity not in allowed:
                excluded[sensitivity] = excluded.get(sensitivity, 0) + 1
                continue

            critical = {}
            for k, v in dict(ctx.get("critical_data_points") or {}).items():
                kind = guess_kind(k)
                if kind == "identity":
                    continue  # ids/commands/paths are identities, not lessons — drop
                critical[k] = bucket_value(v, kind)

            payload = {
                "canvas_type": canvas_type,
                "lesson": sanitize_text(summary, registry),
                "outcome": ctx.get("outcome") or episode.outcome,
                "summary_verification": ctx.get("summary_verification"),
                "summary_source": ctx.get("summary_source"),
                "summary_richness": ctx.get("summary_richness"),
                "visual_elements": ctx.get("visual_elements") or [],
                "user_interaction": sanitize_text(str(ctx.get("user_interaction") or ""), registry),
                "critical_data_points": critical,
                "episode_outcome": episode.outcome or ("success" if episode.success else "failure"),
            }
            items.append({
                "item_id": f"canvas:{segment.episode_id}:{canvas_type}:{dedupe_key[1]}",
                "kind": "canvas_lesson",
                "sensitivity": sensitivity,
                "updated_at": _iso(segment.created_at),
                "payload": payload,
            })
        return items[:MAX_CANVAS_LESSONS], excluded

    # -- facts (LanceDB, best-effort) -----------------------------------------
    def _list_business_facts(self, workspace_id: str) -> List[Dict]:
        try:
            from core.lancedb_service import get_lancedb_handler

            handler = get_lancedb_handler(workspace_id)
            return [doc for doc in handler.list_documents("business_facts", limit=MAX_FACTS + 10)]
        except Exception as e:
            logger.info(f"Business facts unavailable for experience pack ({e})")
            return []

    def _export_facts(self, workspace_id, allowed, registry):
        from core.experience_marketplace.sanitizer import sanitize_text

        items: List[Dict] = []
        excluded: Dict[str, int] = {}
        for doc in self._list_business_facts(workspace_id)[:MAX_FACTS]:
            if not isinstance(doc, dict):
                continue
            meta = doc.get("metadata") or {}
            sensitivity = meta.get("sensitivity", "internal")
            if sensitivity not in allowed:
                excluded[sensitivity] = excluded.get(sensitivity, 0) + 1
                continue
            text = str(doc.get("text") or doc.get("fact") or "")[:2000]
            citations = meta.get("citations") or []
            payload = {
                "fact": sanitize_text(text, registry),
                "domain": meta.get("domain"),
                "verification_status": meta.get("verification_status", "unknown"),
                "citation_count": len(citations) if isinstance(citations, list) else 0,
            }
            items.append({
                "item_id": f"fact:{doc.get('id') or hashlib.sha256(text.encode()).hexdigest()[:16]}",
                "kind": "fact",
                "sensitivity": sensitivity,
                "updated_at": _iso(meta.get("created_at")),
                "payload": payload,
            })
        return items, excluded

    # -- ontology -------------------------------------------------------------
    def _export_ontology(self, db, workspace_id, since_ts, allowed, registry):
        from core.experience_marketplace.sanitizer import bucket_value, guess_kind, sanitize_text

        nodes_q = db.query(GraphNode).filter(GraphNode.workspace_id == workspace_id)
        if since_ts:
            nodes_q = nodes_q.filter(GraphNode.updated_at > since_ts)
        nodes = nodes_q.order_by(GraphNode.updated_at.desc()).limit(MAX_NODES).all()

        node_rows: List[Dict] = []
        excluded: Dict[str, int] = {}
        node_key_map: Dict[Tuple[str, str], str] = {}  # (name, type) -> token
        node_id_map: Dict[str, Tuple[str, str]] = {}  # graph_node.id -> (name, type)
        for node in nodes:
            sensitivity = node.sensitivity or "internal"
            if sensitivity not in allowed:
                excluded[sensitivity] = excluded.get(sensitivity, 0) + 1
                continue
            token = registry.token_for(node.name, node.type or "entity")
            node_key_map[(node.name, node.type or "entity")] = token
            node_id_map[node.id] = (node.name, node.type or "entity")
            node_rows.append({
                "role": token,
                "entity_type": node.type or "entity",
                "description": sanitize_text(node.description or "", registry),
                "sensitivity": sensitivity,
                "updated_at": _iso(node.updated_at or node.created_at),
            })

        chosen = {(n["role"], n["entity_type"]) for n in node_rows}
        token_sensitivity = {n["role"]: n["sensitivity"] for n in node_rows}
        edges_q = db.query(GraphEdge).filter(GraphEdge.workspace_id == workspace_id)
        if since_ts:
            edges_q = edges_q.filter(GraphEdge.created_at > since_ts)
        edge_rows: List[Dict] = []
        skipped_edges = 0
        for edge in edges_q.limit(MAX_EDGES * 4).all():
            source_key = node_id_map.get(edge.source_node_id)
            target_key = node_id_map.get(edge.target_node_id)
            if source_key is None or target_key is None:
                skipped_edges += 1  # endpoint did not survive the node filter
                continue
            s_token, t_token = node_key_map[source_key], node_key_map[target_key]
            if (s_token, source_key[1]) not in chosen or (t_token, target_key[1]) not in chosen:
                skipped_edges += 1
                continue
            props = {}
            for k, v in dict(edge.properties or {}).items():
                props[k] = bucket_value(v, guess_kind(k))
            edge_rows.append({
                "source": [s_token, source_key[1]],
                "target": [t_token, target_key[1]],
                "relationship_type": edge.relationship_type,
                "properties": props,
                "sensitivity": max(
                    token_sensitivity.get(s_token, "internal"),
                    token_sensitivity.get(t_token, "internal"),
                    key=lambda s: SENSITIVITY_LADDER.index(s),
                ),
                "updated_at": _iso(edge.created_at),
            })
            if len(edge_rows) >= MAX_EDGES:
                break
        return {
            "nodes": node_rows,
            "edges": edge_rows,
            "edges_skipped_unresolved": skipped_edges,
        }, excluded

    # -- skills ---------------------------------------------------------------
    def _export_skills(self, db, allowed, registry):
        from core.experience_marketplace.sanitizer import sanitize_text

        items: List[Dict] = []
        excluded: Dict[str, int] = {}
        skills = (
            db.query(Skill)
            .filter(Skill.is_public.is_(True), Skill.is_approved.is_(True))
            .limit(MAX_SKILLS)
            .all()
        )
        for skill in skills:
            if "public" not in allowed:
                excluded["public"] = excluded.get("public", 0) + 1
                continue
            items.append({
                "item_id": f"skill:{skill.id}",
                "kind": "skill",
                "sensitivity": "public",
                "updated_at": _iso(skill.updated_at or skill.created_at),
                "payload": {
                    "name": skill.name,
                    "description": sanitize_text(skill.description or "", registry),
                    "version": skill.version,
                    "category": skill.category,
                    "tags": skill.tags if isinstance(skill.tags, list) else [],
                    "skill_md": (skill.openclaw_skill_md or skill.code or "")[:50_000],
                },
            })
        return items, excluded

    # -------------------------------------------------------------------------
    def _prime_registry(self, db, workspace_id: str, agent_id: str, registry) -> None:
        """Mint role tokens for EVERY identity the agent may reference, BEFORE
        any section is sanitized — patterns/canvas lessons otherwise run against
        an empty registry while ontology names are registered mid-export."""
        names: List[Tuple[str, str]] = []
        try:
            for node_name, node_type in db.query(GraphNode.name, GraphNode.type).filter(
                GraphNode.workspace_id == workspace_id
            ).all():
                if node_name:
                    names.append((node_name, node_type or "entity"))
            for episode in db.query(AgentEpisode.entities).filter(
                AgentEpisode.workspace_id == workspace_id,
                AgentEpisode.agent_id == agent_id,
            ).all():
                entities = episode[0]
                if isinstance(entities, list):
                    for ent in entities:
                        if isinstance(ent, dict) and ent.get("name"):
                            names.append((str(ent["name"]), str(ent.get("type") or "entity")))
        except Exception:
            pass
        for name, entity_type in sorted(set(names)):
            registry.token_for(name, entity_type)

    def export_pack(
        self,
        db: Session,
        workspace_id: str,
        agent_id: str,
        sensitivity_ceiling: str = "internal",
        destination: Optional[str] = None,
        include: Optional[List[str]] = None,
        since: Optional[str] = None,
        tenant_id: Optional[str] = None,
        performed_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assemble + sign a sanitized experience pack for one agent."""
        from core import org_sharing_crypto
        from core.blueprint_sanitizer import has_credentials, strip_credentials
        from core.experience_marketplace.sanitizer import RoleRegistry, scan_for_leak
        from core.ingestion_profile_service import canonical_payload, payload_hash

        if not experience_marketplace_enabled():
            raise PackError("Experience Marketplace is disabled")
        allowed = self._allowed(sensitivity_ceiling)
        if sensitivity_ceiling != "internal" and not destination:
            raise PackError("destination is required when raising the sensitivity ceiling")

        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == workspace_id,
        ).first()
        if agent is None:
            raise PackError("Agent not found in this workspace")

        sections = set(include) if include is not None else set(PACK_SECTIONS)
        unknown = sections - set(PACK_SECTIONS)
        if unknown:
            raise PackError(f"Unknown pack sections: {sorted(unknown)}")

        since_ts = None
        if since:
            try:
                since_ts = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError:
                raise PackError("Invalid since cursor")

        registry = RoleRegistry(db, workspace_id, tenant_id)
        self._prime_registry(db, workspace_id, agent_id, registry)

        section_items: Dict[str, Any] = {}
        section_counts: Dict[str, int] = {}
        excluded_all: Dict[str, int] = {}

        def _merge_excluded(excluded: Dict[str, int]) -> None:
            for k, v in excluded.items():
                excluded_all[k] = excluded_all.get(k, 0) + v

        if "patterns" in sections:
            items, excluded = self._export_patterns(
                db, workspace_id, agent_id, since_ts, allowed, registry
            )
            section_items["patterns"] = items
            section_counts["patterns"] = len(items)
            _merge_excluded(excluded)
        if "canvas_lessons" in sections:
            items, excluded = self._export_canvas_lessons(
                db, workspace_id, agent_id, since_ts, allowed, registry
            )
            section_items["canvas_lessons"] = items
            section_counts["canvas_lessons"] = len(items)
            _merge_excluded(excluded)
        if "facts" in sections:
            items, excluded = self._export_facts(workspace_id, allowed, registry)
            section_items["facts"] = items
            section_counts["facts"] = len(items)
            _merge_excluded(excluded)
        if "ontology" in sections:
            ontology, excluded = self._export_ontology(
                db, workspace_id, since_ts, allowed, registry
            )
            section_items["ontology"] = ontology
            section_counts["ontology"] = len(ontology.get("nodes", [])) + len(ontology.get("edges", []))
            _merge_excluded(excluded)
        if "skills" in sections:
            items, excluded = self._export_skills(db, allowed, registry)
            section_items["skills"] = items
            section_counts["skills"] = len(items)
            _merge_excluded(excluded)

        # Post-assembly leak scan — any surviving identity fragment aborts.
        leaked = scan_for_leak(_collect_texts(section_items, []), registry.names())
        if leaked:
            raise PackError("Refusing to export: identity fragments survived sanitization")

        cursor = {
            "updated_at": max(
                (i.get("updated_at") or "" for sec in section_items.values()
                 for i in _iter_items(sec)),
                default="",
            ),
        }

        payload = {
            "kind": PACK_KIND,
            "pack_version": PACK_VERSION,
            "exported_at": _iso(_now()),
            "source_agent_id": agent_id,
            "source_model": _model_provenance(agent),
            "sensitivity_ceiling": sensitivity_ceiling,
            "delta": bool(since),
            "cursor": cursor,
            "sections": section_items,
        }
        cleaned = strip_credentials(payload)
        if has_credentials(cleaned):
            raise PackError("Refusing to export: credential-shaped keys survived sanitization")

        signature, signed_by = org_sharing_crypto.sign_payload(canonical_payload(cleaned))
        db.add(ExperienceExport(
            workspace_id=workspace_id, tenant_id=tenant_id, agent_id=agent_id,
            sensitivity_ceiling=sensitivity_ceiling, destination=destination,
            sections=sorted(sections), delta=bool(since),
            item_count=sum(section_counts.values()), section_counts=section_counts,
            excluded_by_sensitivity=excluded_all, payload_hash=payload_hash(cleaned),
            signature=signature, signed_by=signed_by, performed_by=performed_by,
        ))
        db.commit()

        return {
            "kind": PACK_KIND,
            "payload": cleaned,
            "payload_hash": payload_hash(cleaned),
            "signature": signature,
            "signed_by": signed_by,
            "excluded_by_sensitivity": excluded_all,
            "section_counts": section_counts,
        }

    # -------------------------------------------------------------------------
    async def import_pack(
        self,
        db: Session,
        envelope: Dict[str, Any],
        workspace_id: str,
        tenant_id: Optional[str] = None,
        performed_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify + idempotently import a signed experience pack."""
        from core import org_sharing_crypto
        from core.blueprint_sanitizer import has_credentials, strip_credentials
        from core.data_taint_tracker import higher_sensitivity
        from core.ingestion_profile_service import canonical_payload, payload_hash
        from core.blueprint_sanitizer import has_credentials as _has_creds

        if not experience_marketplace_enabled():
            raise PackError("Experience Marketplace is disabled")
        if not isinstance(envelope, dict) or envelope.get("kind") != PACK_KIND:
            raise PackError("Not an Atom experience pack (bad kind)")
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise PackError("Pack envelope has no payload")
        if payload.get("pack_version") != PACK_VERSION:
            raise PackError(f"Unsupported pack_version {payload.get('pack_version')!r}")

        # Verify BEFORE parsing — hash then signature (fail closed).
        source_agent_id = payload.get("source_agent_id")

        def _audit_failure(reason: str) -> None:
            db.add(ExperienceImport(
                workspace_id=workspace_id, tenant_id=tenant_id,
                source_agent_id=source_agent_id,
                payload_hash=str(envelope.get("payload_hash", "")),
                signature_valid=False, signature_strip_credentials=False,
                item_total=0, failure_reason=reason, performed_by=performed_by,
            ))
            db.commit()

        try:
            if payload_hash(payload) != envelope.get("payload_hash", ""):
                raise PackError("Payload hash mismatch — pack was tampered with")
            if not envelope.get("signature"):
                raise PackError("Pack is not signed")
            if not org_sharing_crypto.verify_payload(
                db, canonical_payload(payload), str(envelope["signature"]), workspace_id
            ):
                raise PackError("Pack signature verification failed (signer not in key registry)")
        except PackError as e:
            _audit_failure("signature_verification_failed")
            raise

        # Defense in depth: re-sanitize on import.
        payload = strip_credentials(payload)
        if has_credentials(payload):
            db.add(ExperienceImport(
                workspace_id=workspace_id, tenant_id=tenant_id,
                source_agent_id=payload.get("source_agent_id"),
                payload_hash=str(envelope.get("payload_hash", "")),
                signature_valid=True, signature_strip_credentials=False,
                item_total=0, failure_reason="credential_shaped_data", performed_by=performed_by,
            ))
            db.commit()
            raise PackError("Credential-shaped data in pack")

        declared_ceiling = payload.get("sensitivity_ceiling", "internal")
        if declared_ceiling not in SENSITIVITY_LADDER:
            raise PackError("Invalid sensitivity ceiling in pack")
        allowed = set(SENSITIVITY_LADDER[: SENSITIVITY_LADDER.index(declared_ceiling) + 1])

        source_agent_id = payload.get("source_agent_id") or "unknown"
        # WikiSkill W6: the exporter's model rides with the pack; every
        # applied item is stamped with it and QUARANTINED until validated on
        # this installation (transfer_safety), because skills evolved by a
        # weaker model can degrade a stronger one catastrophically.
        source_model = str(payload.get("source_model") or "unknown")[:255]
        sections = payload.get("sections") or {}
        applied = 0
        skipped = 0
        excluded = 0
        tombstones = 0
        nodes_applied = 0
        edges_applied = 0
        edges_skipped = 0
        section_counts: Dict[str, int] = {}

        for kind in ITEM_KINDS:
            items = sections.get(kind + "s")
            if not isinstance(items, list):
                continue
            section_counts[kind] = len(items)
            for item in items:
                if not isinstance(item, dict) or not item.get("item_id"):
                    skipped += 1
                    continue
                sensitivity = item.get("sensitivity", "internal")
                if sensitivity not in allowed:
                    excluded += 1
                    continue
                item_payload = strip_credentials(dict(item.get("payload") or {}))
                if _has_creds(item_payload):
                    excluded += 1
                    continue
                ch = payload_hash(item_payload)
                existing = db.query(ExperienceItem).filter(
                    ExperienceItem.workspace_id == workspace_id,
                    ExperienceItem.source_agent_id == source_agent_id,
                    ExperienceItem.item_id == item["item_id"],
                ).first()
                if existing is not None:
                    if existing.content_hash == ch:
                        skipped += 1
                        continue
                    existing.payload = item_payload
                    existing.content_hash = ch
                    existing.sensitivity = sensitivity
                    existing.source_model = source_model
                    # Changed content is new knowledge: re-quarantine until
                    # validated on this installation (W6).
                    existing.validation_state = "pending"
                    existing.updated_at = _now()
                    applied += 1
                    continue
                db.add(ExperienceItem(
                    workspace_id=workspace_id, tenant_id=tenant_id,
                    source_agent_id=source_agent_id, kind=item.get("kind") or kind,
                    item_id=item["item_id"], sensitivity=sensitivity,
                    payload=item_payload, content_hash=ch,
                    imported_from=performed_by or "experience_pack",
                    source_model=source_model,
                    validation_state="pending",
                ))
                applied += 1

            tombstones_list = sections.get(kind + "s_tombstones") or []
            for tombstone in tombstones_list:
                if not isinstance(tombstone, dict) or not tombstone.get("item_id"):
                    continue
                row = db.query(ExperienceItem).filter(
                    ExperienceItem.workspace_id == workspace_id,
                    ExperienceItem.source_agent_id == source_agent_id,
                    ExperienceItem.item_id == tombstone["item_id"],
                ).first()
                if row is not None and row.superseded_at is None:
                    row.superseded_at = _now()
                    tombstones += 1

        ontology = sections.get("ontology")
        if isinstance(ontology, dict):
            nodes = ontology.get("nodes") or []
            section_counts["ontology_nodes"] = len(nodes)
            node_ids: Dict[Tuple[str, str], str] = {}  # (token, type) -> graph_nodes.id
            for node in nodes:
                token = node.get("role")
                entity_type = node.get("entity_type") or "entity"
                if not token or node.get("sensitivity", "internal") not in allowed:
                    excluded += 1
                    continue
                sensitivity = node.get("sensitivity", "internal")
                existing = db.query(GraphNode).filter(
                    GraphNode.workspace_id == workspace_id,
                    GraphNode.name == token,
                    GraphNode.type == entity_type,
                ).first()
                if existing is None:
                    row = GraphNode(
                        workspace_id=workspace_id, tenant_id=tenant_id,
                        name=token, type=entity_type,
                        description=node.get("description") or "",
                        sensitivity=sensitivity,
                    )
                    db.add(row)
                    db.flush()
                    node_ids[(token, entity_type)] = row.id
                    nodes_applied += 1
                else:
                    existing.description = node.get("description") or existing.description
                    existing.sensitivity = higher_sensitivity(
                        existing.sensitivity or "internal", sensitivity
                    )
                    node_ids[(token, entity_type)] = existing.id
                    nodes_applied += 1

            source_map = {(n.get("role"), n.get("entity_type")): True for n in nodes}
            section_counts["ontology_edges"] = len(ontology.get("edges") or [])
            for edge in ontology.get("edges") or []:
                s_kind = edge.get("source") or []
                t_kind = edge.get("target") or []
                if len(s_kind) != 2 or len(t_kind) != 2:
                    edges_skipped += 1
                    continue
                s_token, s_type = s_kind
                t_token, t_type = t_kind
                if (s_token, s_type) not in source_map or (t_token, t_type) not in source_map:
                    edges_skipped += 1
                    continue  # no stub nodes
                source_id = node_ids.get((s_token, s_type))
                target_id = node_ids.get((t_token, t_type))
                if not source_id or not target_id:
                    edges_skipped += 1
                    continue
                existing = db.query(GraphEdge).filter(
                    GraphEdge.workspace_id == workspace_id,
                    GraphEdge.source_node_id == source_id,
                    GraphEdge.target_node_id == target_id,
                    GraphEdge.relationship_type == edge.get("relationship_type"),
                ).first()
                if existing is None:
                    db.add(GraphEdge(
                        workspace_id=workspace_id, tenant_id=tenant_id,
                        source_node_id=source_id, target_node_id=target_id,
                        relationship_type=edge.get("relationship_type") or "RELATES_TO",
                        properties=edge.get("properties") or {},
                    ))
                edges_applied += 1  # idempotent either way

        db.add(ExperienceImport(
            workspace_id=workspace_id, tenant_id=tenant_id,
            source_agent_id=source_agent_id,
            payload_hash=str(envelope.get("payload_hash", "")),
            signature_valid=True, signature_strip_credentials=True,
            sensitivity_ceiling=declared_ceiling,
            item_total=applied + skipped + excluded,
            item_applied=applied, item_skipped=skipped, item_excluded=excluded,
            tombstones_applied=tombstones, nodes_applied=nodes_applied,
            edges_applied=edges_applied, edges_skipped=edges_skipped,
            section_counts=section_counts, performed_by=performed_by,
        ))
        db.commit()

        if payload.get("delta") and isinstance(payload.get("cursor"), dict):
            _store_cursor(db, workspace_id, payload["cursor"])

        return {
            "applied": applied, "skipped": skipped, "excluded": excluded,
            "tombstones": tombstones, "nodes": nodes_applied, "edges": edges_applied,
            "edges_skipped": edges_skipped, "section_counts": section_counts,
        }

    # -------------------------------------------------------------------------
    def reputation_for_agent(self, db: Session, workspace_id: str, agent_id: str) -> Dict[str, Any]:
        if not experience_marketplace_enabled():
            raise PackError("Experience Marketplace is disabled")
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == workspace_id,
        ).first()
        if agent is None:
            raise PackError("Agent not found in this workspace")

        episodes = db.query(AgentEpisode).filter(
            AgentEpisode.workspace_id == workspace_id,
            AgentEpisode.agent_id == agent_id,
        ).all()
        total = len(episodes)
        outcomes: Dict[str, int] = {}
        ratings = [e.supervisor_rating for e in episodes if e.supervisor_rating is not None]
        feedback = [e.aggregate_feedback_score for e in episodes if e.aggregate_feedback_score is not None]
        efficiency = [e.step_efficiency for e in episodes if e.step_efficiency is not None]
        success = 0
        for ep in episodes:
            outcome = ep.outcome or ("success" if ep.success else "failure")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            if outcome == "success":
                success += 1

        # Verified step count (graduation gate) + export count.
        verified_steps = 0
        try:
            execution_ids = [e.execution_id for e in episodes if e.execution_id]
            if execution_ids:
                verified_steps = db.query(func.count()).filter(
                    AgentReasoningStep.execution_id.in_(execution_ids),
                    AgentReasoningStep.verified == "verified",
                ).scalar() or 0
        except Exception:
            pass
        export_count = db.query(func.count()).filter(
            ExperienceExport.workspace_id == workspace_id,
            ExperienceExport.agent_id == agent_id,
        ).scalar() or 0

        avg = lambda xs: (sum(xs) / len(xs)) if xs else None  # noqa: E731
        tier = "STUDENT"
        if verified_steps >= 50:
            tier = "AUTONOMOUS"
        elif verified_steps >= 20:
            tier = "SUPERVISED"
        elif verified_steps >= 5:
            tier = "INTERN"
        last_episode = max((e.updated_at or e.created_at for e in episodes), default=None)
        return {
            "agent_id": agent_id,
            "maturity": tier,
            "episodes_total": total,
            "success_rate": round(success / total, 3) if total else None,
            "outcome_breakdown": outcomes,
            "verified_execution_count": verified_steps,
            "avg_supervisor_rating": avg(ratings),
            "avg_feedback_score": avg(feedback),
            "avg_step_efficiency": avg(efficiency),
            "export_count": export_count,
            "last_episode_at": _iso(last_episode),
        }

    def list_reputations(self, db: Session, workspace_id: str, limit: int = 50) -> List[Dict]:
        if not experience_marketplace_enabled():
            raise PackError("Experience Marketplace is disabled")
        agent_ids = [
            row[0] for row in db.query(AgentEpisode.agent_id)
            .filter(AgentEpisode.workspace_id == workspace_id)
            .distinct().limit(limit).all()
        ]
        cards: List[Dict] = []
        for agent_id in agent_ids:
            try:
                cards.append(self.reputation_for_agent(db, workspace_id, agent_id))
            except PackError:
                continue
        return cards