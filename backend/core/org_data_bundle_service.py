"""Org Data Bundle Service — opt-in sharing of ingested *data* within an org.

Org Ingestion Sharing Phase 2
(docs/architecture/ORG_INGESTION_SHARING_PLAN.md): exports normalized
ingested records as a signed JSON bundle that another member's local instance
imports. Bundles carry **normalized records only** — never credentials
(P5 sanitizer, fail-closed) and never embeddings (instances run different
embedding providers under BYOK; the importer re-embeds locally through the
normal governed ingestion paths).

Sensitivity gate (P4 classifications): records classified ``confidential`` or
``restricted`` are excluded by default and can only leave via an explicitly
raised ceiling (a scoped sub-bundle for e.g. the finance team).

Idempotent imports: the ``document_ingestions`` unique (workspace_id, doc_id)
row is the dedup key; unchanged records are skipped, changed ones re-ingested.
Tombstones propagate source deletions (GDPR erasure) — imports mark matching
documents ``freshness_status='removed'``.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.blueprint_sanitizer import has_credentials, strip_credentials

logger = logging.getLogger(__name__)

BUNDLE_VERSION = 2  # v1 = records only; v2 adds graph + texts sections
SUPPORTED_BUNDLE_VERSIONS = (1, 2)
BUNDLE_KIND = "atom_org_data_bundle"

# Ladder from least to most sensitive (P4 data-taint classifications).
SENSITIVITY_LADDER = ["public", "internal", "confidential", "restricted"]

# Caps mirror the mini-app store caps philosophy: bounded sharing payloads.
MAX_RECORDS_PER_BUNDLE = 100_000
MAX_PREVIEW_CHARS = 20_000
# Phase 2b caps.
MAX_NODES_PER_BUNDLE = 50_000
MAX_EDGES_PER_BUNDLE = 200_000
MAX_TEXTS_PER_BUNDLE = 10_000
BUNDLE_SECTIONS = ("records", "graph", "texts")


def _sensitivity_rank(value: Optional[str]) -> int:
    try:
        return SENSITIVITY_LADDER.index(value or "internal")
    except ValueError:
        return SENSITIVITY_LADDER.index("internal")


def _max_sensitivity(a: Optional[str], b: Optional[str]) -> str:
    """The more restrictive of two classifications — never lowers."""
    return a if _sensitivity_rank(a) >= _sensitivity_rank(b) else b


class BundleError(ValueError):
    """Raised for structurally invalid/unsafe bundles (never swallowed)."""


def _content_hash(record: Dict[str, Any]) -> str:
    basis = "|".join(str(record.get(k) or "") for k in
                     ("integration_id", "external_id", "external_modified_at", "content_preview"))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _doc_id(integration_id: str, external_id: str) -> str:
    return f"{integration_id}:{external_id}"


def sign_and_audit_bundle(
    db: Session,
    payload: Dict[str, Any],
    workspace_id: str,
    sources: List[str],
    destination: Optional[str] = None,
    section_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Sanitize (fail-closed), sign, audit, and envelope a bundle payload.

    Shared by the snapshot export (``build_bundle``) and the Phase 3 hub
    delta export (``core.org_hub_service``): both must go through the same
    strip_credentials gate, Ed25519 signing, and ``bundle_exports`` audit row.
    """
    from core import org_sharing_crypto
    from core.ingestion_profile_service import canonical_payload, payload_hash
    from core.models import BundleExport

    cleaned = strip_credentials(payload)
    if has_credentials(cleaned):
        raise BundleError("Refusing to export bundle: credential-shaped keys survived sanitization")

    signature, signed_by = org_sharing_crypto.sign_payload(canonical_payload(cleaned))

    db.add(BundleExport(
        workspace_id=workspace_id,
        payload_hash=payload_hash(cleaned),
        sources=list(sources),
        record_count=len(cleaned.get("records", [])),
        sensitivity_breakdown=cleaned.get("sensitivity_breakdown", {}),
        section_counts=section_counts,
        destination=destination,
    ))
    db.commit()

    return {
        "kind": BUNDLE_KIND,
        "payload": cleaned,
        "payload_hash": payload_hash(cleaned),
        "signature": signature,
        "signed_by": signed_by,
    }


class OrgDataBundleService:
    """Export/import signed org data bundles between member instances."""

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def build_bundle(
        self,
        db: Session,
        workspace_id: str,
        sources: List[str],
        sensitivity_ceiling: str = "internal",
        destination: Optional[str] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Assemble + sign the bundle envelope for the selected sources.

        ``sensitivity_ceiling`` is the highest sensitivity allowed in the
        bundle (ladder: public < internal < confidential < restricted).
        Default ``internal`` — confidential/restricted never leave by default.

        ``include`` selects payload sections (records | graph | texts);
        default all three. ``graph`` shares GraphRAG nodes/edges (rows, never
        embeddings); ``texts`` shares knowledge documents + business facts.
        """
        from core import org_sharing_crypto
        from core.models import BundleExport, IngestedDocument

        if sensitivity_ceiling not in SENSITIVITY_LADDER:
            raise BundleError(f"Invalid sensitivity_ceiling {sensitivity_ceiling!r}")
        allowed = set(SENSITIVITY_LADDER[: SENSITIVITY_LADDER.index(sensitivity_ceiling) + 1])

        sections = set(include) if include is not None else set(BUNDLE_SECTIONS)
        unknown = sections - set(BUNDLE_SECTIONS)
        if unknown:
            raise BundleError(f"Unknown bundle sections: {sorted(unknown)}")

        query = db.query(IngestedDocument).filter(
            IngestedDocument.workspace_id == workspace_id
        )
        if sources:
            query = query.filter(IngestedDocument.integration_id.in_(sources))

        records: List[Dict[str, Any]] = []
        breakdown: Dict[str, int] = {}
        excluded: Dict[str, int] = {}
        if "records" in sections:
            for doc in query.yield_per(1000):
                sensitivity = doc.sensitivity or "internal"
                if sensitivity not in allowed:
                    excluded[sensitivity] = excluded.get(sensitivity, 0) + 1
                    continue
                preview = (doc.content_preview or "")[:MAX_PREVIEW_CHARS]
                record = {
                    "integration_id": doc.integration_id,
                    "external_id": doc.external_id,
                    "file_name": doc.file_name,
                    "file_type": doc.file_type,
                    "content_preview": preview,
                    "external_modified_at": doc.external_modified_at.isoformat() if doc.external_modified_at else None,
                    "sensitivity": sensitivity,
                    "content_hash": _content_hash({
                        "integration_id": doc.integration_id,
                        "external_id": doc.external_id,
                        "external_modified_at": doc.external_modified_at.isoformat() if doc.external_modified_at else None,
                        "content_preview": preview,
                    }),
                }
                records.append(record)
                breakdown[sensitivity] = breakdown.get(sensitivity, 0) + 1
                if len(records) >= MAX_RECORDS_PER_BUNDLE:
                    logger.warning(f"Bundle record cap ({MAX_RECORDS_PER_BUNDLE}) reached — truncating")
                    break

        graph_section = self._build_graph_section(db, workspace_id, allowed) if "graph" in sections else None
        texts_section, texts_note = self._build_texts_section(db, workspace_id, allowed) if "texts" in sections else (None, None)

        section_counts = {"records": len(records)}
        if graph_section is not None:
            section_counts["nodes"] = len(graph_section["nodes"])
            section_counts["edges"] = len(graph_section["edges"])
        if texts_section is not None:
            section_counts["knowledge_documents"] = len(texts_section.get("knowledge_documents", []))
            section_counts["business_facts"] = len(texts_section.get("business_facts", []))

        payload = {
            "kind": BUNDLE_KIND,
            "bundle_version": BUNDLE_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "workspace_id": workspace_id,
            "sources": list(sources),
            "sensitivity_ceiling": sensitivity_ceiling,
            "records": records,
            "tombstones": [],
            "sensitivity_breakdown": breakdown,
        }
        if graph_section is not None:
            payload["graph"] = graph_section
        if texts_section is not None:
            payload["texts"] = texts_section
            if texts_note:
                payload["texts_note"] = texts_note

        envelope = sign_and_audit_bundle(
            db,
            payload,
            workspace_id=workspace_id,
            sources=sources,
            destination=destination,
            section_counts=section_counts,
        )
        if excluded:
            envelope["excluded_by_sensitivity"] = excluded
        return envelope

    # ------------------------------------------------------------------
    # Phase 2b section builders (graph + texts)
    # ------------------------------------------------------------------

    def _build_graph_section(
        self, db: Session, workspace_id: str, allowed: set
    ) -> Dict[str, Any]:
        """Export GraphRAG nodes/edges as portable rows.

        Nodes are keyed by ``(name, type)`` — never local UUIDs, never the
        derived ``embedding`` column. An edge is exported only when BOTH
        endpoints pass the sensitivity filter (an edge into a restricted node
        leaks its existence).
        """
        from core.models import GraphEdge, GraphNode

        nodes_query = db.query(GraphNode).filter(GraphNode.workspace_id == workspace_id)
        exported_keys: set = set()
        nodes: List[Dict[str, Any]] = []
        id_to_key: Dict[str, List[str]] = {}
        for node in nodes_query.yield_per(1000):
            sensitivity = node.sensitivity or "internal"
            if sensitivity not in allowed:
                continue
            key = [node.name, node.type]
            id_to_key[node.id] = key
            if tuple(key) in exported_keys:
                continue
            exported_keys.add(tuple(key))
            nodes.append({
                "key": key,
                "name": node.name,
                "type": node.type,
                "description": node.description or "",
                "properties": dict(node.properties or {}),
                "sensitivity": sensitivity,
                "source_updated_at": node.updated_at.isoformat() if node.updated_at else None,
                "content_hash": hashlib.sha256(
                    f"{node.name}|{node.type}|{node.description or ''}|{node.updated_at or ''}"
                    .encode("utf-8")).hexdigest(),
            })
            if len(nodes) >= MAX_NODES_PER_BUNDLE:
                logger.warning(f"Bundle node cap ({MAX_NODES_PER_BUNDLE}) reached — truncating")
                break

        edges: List[Dict[str, Any]] = []
        edges_query = db.query(GraphEdge).filter(GraphEdge.workspace_id == workspace_id)
        for edge in edges_query.yield_per(1000):
            src = id_to_key.get(edge.source_node_id)
            tgt = id_to_key.get(edge.target_node_id)
            if src is None or tgt is None:
                continue  # endpoint filtered out (or missing) — edge must not leak it
            edges.append({
                "source_key": src,
                "target_key": tgt,
                "relationship_type": edge.relationship_type,
                "weight": edge.weight if edge.weight is not None else 1.0,
                "properties": dict(edge.properties or {}),
            })
            if len(edges) >= MAX_EDGES_PER_BUNDLE:
                logger.warning(f"Bundle edge cap ({MAX_EDGES_PER_BUNDLE}) reached — truncating")
                break

        return {"nodes": nodes, "edges": edges}

    def _build_texts_section(
        self, db: Session, workspace_id: str, allowed: set
    ) -> tuple:
        """Export knowledge documents (SQL) + business facts (LanceDB).

        Returns ``(section, note)`` — ``note`` is set when the LanceDB facts
        table was unavailable (best-effort; never blocks the export).
        """
        from core.models import KnowledgeDocument

        knowledge_docs: List[Dict[str, Any]] = []
        kd_query = db.query(KnowledgeDocument).filter(
            (KnowledgeDocument.workspace_id == workspace_id)
            | (KnowledgeDocument.workspace_id.is_(None))
        )
        for kd in kd_query.yield_per(200):
            sensitivity = kd.sensitivity or "internal"
            if sensitivity not in allowed:
                continue
            knowledge_docs.append({
                "title": kd.title or "",
                "content": kd.content or "",
                "doc_type": kd.doc_type or "text",
                "sensitivity": sensitivity,
                "content_hash": hashlib.sha256((kd.content or "").encode("utf-8")).hexdigest(),
            })
            if len(knowledge_docs) >= MAX_TEXTS_PER_BUNDLE:
                logger.warning(f"Bundle text cap ({MAX_TEXTS_PER_BUNDLE}) reached — truncating")
                break

        business_facts: List[Dict[str, Any]] = []
        note = None
        try:
            from core.lancedb_handler import get_lancedb_handler
            handler = get_lancedb_handler(workspace_id)
            for doc in handler.list_documents("business_facts", limit=MAX_TEXTS_PER_BUNDLE):
                metadata = doc.get("metadata") or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                sensitivity = metadata.get("sensitivity", "internal")
                if sensitivity not in allowed:
                    continue
                business_facts.append({
                    "fact_id": doc.get("id"),
                    "text": doc.get("text", ""),
                    "sensitivity": sensitivity,
                    "metadata": metadata,
                })
        except Exception as e:
            note = f"business_facts unavailable: {e}"
            logger.warning(f"Bundle texts: {note}")

        return {
            "knowledge_documents": knowledge_docs,
            "business_facts": business_facts,
        }, note

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    async def apply_bundle(
        self,
        db: Session,
        envelope: Dict[str, Any],
        workspace_id: str,
        tenant_id: Optional[str] = None,
        performed_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify + import a bundle. Signature check happens BEFORE parsing records."""
        from core import org_sharing_crypto
        from core.models import BundleImport, DocumentIngestion, IngestedDocument
        from core.ingestion_profile_service import canonical_payload, payload_hash

        if not isinstance(envelope, dict) or envelope.get("kind") != BUNDLE_KIND:
            raise BundleError("Not an Atom org data bundle (bad kind)")
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise BundleError("Bundle envelope has no payload")
        if payload.get("bundle_version") not in SUPPORTED_BUNDLE_VERSIONS:
            raise BundleError(f"Unsupported bundle_version {payload.get('bundle_version')!r}")

        # Verify BEFORE parsing: hash match then signature. Rejected bundles
        # are ALWAYS audited (plan §6: "unverified bundles are rejected and
        # audited") — the audit row records the failure for later review.
        try:
            if payload_hash(payload) != envelope.get("payload_hash", ""):
                raise BundleError("Payload hash mismatch — bundle was tampered with")
            if not envelope.get("signature"):
                raise BundleError("Bundle is not signed")
            if not org_sharing_crypto.verify_payload(
                db, canonical_payload(payload), str(envelope["signature"]), workspace_id
            ):
                raise BundleError(
                    "Bundle signature verification failed (signer not in org key registry)"
                )
        except BundleError:
            db.add(BundleImport(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                payload_hash=str(envelope.get("payload_hash", "")),
                records_total=0,
                records_ingested=0,
                records_skipped=0,
                tombstones_applied=0,
                performed_by=performed_by,
            ))
            db.commit()
            raise

        # Defense in depth: sanitize again on import.
        payload = strip_credentials(payload)
        records = payload.get("records", [])
        if not isinstance(records, list):
            raise BundleError("Bundle records must be a list")
        if len(records) > MAX_RECORDS_PER_BUNDLE:
            raise BundleError(f"Bundle exceeds record cap ({MAX_RECORDS_PER_BUNDLE})")
        tombstones = payload.get("tombstones", []) or []

        # Best-effort local re-embedding through the governed path (same
        # to_thread pattern as HybridDataIngestionService).
        memory_handler = None
        try:
            from core.lancedb_handler import get_lancedb_handler
            memory_handler = get_lancedb_handler(workspace_id)
        except Exception as e:
            logger.warning(f"LanceDB handler unavailable for bundle import re-embedding: {e}")

        ingested = 0
        skipped = 0
        errors: List[str] = []
        # R84: records now also derive deterministic business facts locally
        # (LLM-free — importing 100k records must never bill). One budget
        # per import caps total fact rows; unchanged re-imports skip via
        # the bridge's DocumentIngestion markers.
        try:
            from core.integration_ontology_bridge import FactBudget, write_integration_fact
            record_fact_budget = FactBudget()
        except Exception as e:  # noqa: BLE001 — fact layer must never block import
            logger.warning(f"Fact bridge unavailable for bundle import: {e}")
            record_fact_budget = None
        facts_written = 0
        for record in records:
            integration_id = record.get("integration_id")
            external_id = record.get("external_id")
            if not integration_id or not external_id:
                skipped += 1
                continue
            try:
                doc_id = _doc_id(str(integration_id), str(external_id))
                new_hash = record.get("content_hash") or _content_hash(record)

                dedup = db.query(DocumentIngestion).filter(
                    DocumentIngestion.workspace_id == workspace_id,
                    DocumentIngestion.doc_id == doc_id,
                ).first()

                # Upsert the normalized document row.
                doc = db.query(IngestedDocument).filter(
                    IngestedDocument.workspace_id == workspace_id,
                    IngestedDocument.integration_id == integration_id,
                    IngestedDocument.external_id == external_id,
                ).first()
                if dedup and doc and dedup.content_hash == new_hash:
                    skipped += 1  # unchanged since last import
                    continue

                modified = record.get("external_modified_at")
                if doc is None:
                    doc = IngestedDocument(
                        workspace_id=workspace_id,
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                        external_id=external_id,
                        file_name=record.get("file_name") or f"{external_id}",
                        file_path=record.get("file_name") or "",
                        file_type=record.get("file_type") or "unknown",
                    )
                    db.add(doc)
                doc.file_name = record.get("file_name") or doc.file_name
                doc.content_preview = record.get("content_preview")
                doc.sensitivity = record.get("sensitivity", "internal")
                doc.external_modified_at = datetime.fromisoformat(modified) if modified else None
                doc.updated_at = datetime.now(timezone.utc)

                if dedup is None:
                    dedup = DocumentIngestion(
                        workspace_id=workspace_id,
                        doc_id=doc_id,
                        content_hash=new_hash,
                        source=str(integration_id),
                    )
                    db.add(dedup)
                else:
                    dedup.content_hash = new_hash
                db.commit()
                ingested += 1

                if memory_handler and record.get("content_preview"):
                    try:
                        await asyncio.to_thread(
                            memory_handler.add_document,
                            table_name=f"integration_{integration_id}",
                            text=str(record["content_preview"]),
                            source=f"org_bundle:{integration_id}",
                            metadata={
                                "integration_id": integration_id,
                                "record_id": external_id,
                                "imported_via": "org_data_bundle",
                                "imported_at": datetime.now(timezone.utc).isoformat(),
                            },
                            user_id="org_import",
                        )
                    except Exception as embed_err:
                        errors.append(f"embed:{doc_id}:{embed_err}")

                # R84: derive the deterministic business fact for this
                # newly-ingested record (bundle records carry no record
                # type → generic template; sensitivity comes from the
                # bundle row, never reclassified).
                if record_fact_budget is not None and record.get("content_preview"):
                    try:
                        fact_stats = await write_integration_fact(
                            workspace_id=workspace_id,
                            tenant_id=tenant_id,
                            integration_id=str(integration_id),
                            record_type=None,
                            record={
                                "id": str(external_id),
                                "title": record.get("file_name"),
                            },
                            text=str(record["content_preview"]),
                            sensitivity=record.get("sensitivity", "internal"),
                            memory_handler=memory_handler,
                            budget=record_fact_budget,
                        )
                        facts_written += fact_stats.get("written", 0)
                    except Exception as fact_err:  # noqa: BLE001
                        errors.append(f"fact:{doc_id}:{fact_err}")
            except Exception as record_err:
                errors.append(str(record_err))
                logger.warning(f"Bundle record import failed for {integration_id}/{external_id}: {record_err}")

        tombstones_applied = 0
        # R84: group tombstoned records by integration so each derived
        # business fact (intfact:{integration}:{record}) can be retracted
        # — a removed record's observation is no longer citable.
        _tombstoned_by_integration: Dict[str, List[str]] = {}
        for external_id in tombstones:
            doc = db.query(IngestedDocument).filter(
                IngestedDocument.workspace_id == workspace_id,
                IngestedDocument.external_id == external_id,
            ).first()
            if doc:
                doc.freshness_status = "removed"
                if getattr(doc, "integration_id", None):
                    _tombstoned_by_integration.setdefault(
                        str(doc.integration_id), []
                    ).append(str(external_id))
                tombstones_applied += 1
        db.commit()

        facts_retracted = 0
        for _tomb_integration, _tomb_records in _tombstoned_by_integration.items():
            try:
                from core.integration_ontology_bridge import (
                    retract_integration_facts,
                )

                retract_result = await retract_integration_facts(
                    workspace_id=workspace_id,
                    integration_id=_tomb_integration,
                    record_ids=_tomb_records,
                    memory_handler=memory_handler,
                )
                facts_retracted += int(retract_result.get("retracted", 0))
            except Exception as e:  # noqa: BLE001 — retraction never blocks import
                logger.warning(f"Fact retraction after tombstones failed: {e}")

        # --- Phase 2b sections ---
        graph_result = {"nodes_ingested": 0, "nodes_skipped": 0, "edges_ingested": 0,
                        "edges_skipped_unresolved": 0}
        if isinstance(payload.get("graph"), dict):
            graph_result = self._apply_graph_section(db, payload["graph"], workspace_id, tenant_id)
        texts_result = {"knowledge_ingested": 0, "knowledge_skipped": 0,
                        "facts_ingested": 0, "facts_skipped": 0}
        if isinstance(payload.get("texts"), dict):
            texts_result = await self._apply_texts_section(
                db, payload["texts"], workspace_id, tenant_id, memory_handler
            )

        # Imported communities are never trusted: recompute locally from the
        # merged graph (best-effort, off the event loop).
        communities_rebuilt = False
        if isinstance(payload.get("graph"), dict):
            try:
                from core.graphrag_engine import GraphRAGEngine
                engine = GraphRAGEngine(workspace_id=workspace_id, tenant_id=tenant_id or "default")
                result = await asyncio.to_thread(engine.build_communities, workspace_id)
                communities_rebuilt = bool(result.get("success"))
            except Exception as e:
                logger.warning(f"Community recompute after bundle import failed: {e}")

        section_counts = {
            "records": {"ingested": ingested, "skipped": skipped,
                        "facts_written": facts_written},
            **{k: v for k, v in graph_result.items()},
            **{k: v for k, v in texts_result.items()},
        }

        db.add(BundleImport(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            payload_hash=envelope.get("payload_hash", ""),
            records_total=len(records),
            records_ingested=ingested,
            records_skipped=skipped,
            tombstones_applied=tombstones_applied,
            section_counts=section_counts,
            performed_by=performed_by,
        ))
        db.commit()

        return {
            "records_total": len(records),
            "records_ingested": ingested,
            "records_skipped": skipped,
            "facts_written": facts_written,
            "facts_retracted": facts_retracted,
            "tombstones_applied": tombstones_applied,
            "graph": graph_result,
            "texts": texts_result,
            "communities_rebuilt": communities_rebuilt,
            "errors": errors[:20],
        }

    # ------------------------------------------------------------------
    # Phase 2b import sections
    # ------------------------------------------------------------------

    def _apply_graph_section(
        self,
        db: Session,
        graph: Dict[str, Any],
        workspace_id: str,
        tenant_id: Optional[str],
    ) -> Dict[str, int]:
        """Merge nodes/edges into the local graph.

        Nodes upsert on ``(workspace_id, name, type)``: bundle wins if its
        ``source_updated_at`` is newer; sensitivity is raised to the max of
        local/imported (never lowered). Edges resolve endpoint keys against
        local nodes — unresolved endpoints are skipped and counted; **no stub
        nodes are ever created** (an import must not fabricate entities the
        importer never saw text for).
        """
        from core.models import GraphEdge, GraphNode

        stats = {"nodes_ingested": 0, "nodes_skipped": 0, "edges_ingested": 0,
                 "edges_skipped_unresolved": 0}
        key_to_id: Dict[tuple, str] = {}

        for node_data in graph.get("nodes", []):
            key = node_data.get("key") or [node_data.get("name"), node_data.get("type")]
            if not key or len(key) != 2 or not key[0] or not key[1]:
                stats["nodes_skipped"] += 1
                continue
            try:
                existing = db.query(GraphNode).filter(
                    GraphNode.workspace_id == workspace_id,
                    GraphNode.name == key[0],
                    GraphNode.type == key[1],
                ).first()

                incoming_updated = None
                if node_data.get("source_updated_at"):
                    try:
                        incoming_updated = datetime.fromisoformat(node_data["source_updated_at"])
                    except ValueError:
                        pass

                if existing is None:
                    existing = GraphNode(
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        name=key[0],
                        type=key[1],
                        description=node_data.get("description", ""),
                        properties=dict(node_data.get("properties") or {}),
                        sensitivity=node_data.get("sensitivity", "internal"),
                    )
                    db.add(existing)
                    db.flush()
                    stats["nodes_ingested"] += 1
                else:
                    def _utc(dt):
                        return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt
                    local_updated = _utc(existing.updated_at or existing.created_at)
                    incoming_updated = _utc(incoming_updated)
                    bundle_newer = (
                        incoming_updated is not None
                        and (local_updated is None or incoming_updated > local_updated)
                    )
                    if bundle_newer:
                        if node_data.get("description"):
                            existing.description = node_data["description"]
                        merged_props = dict(existing.properties or {})
                        merged_props.update(node_data.get("properties") or {})
                        existing.properties = merged_props
                    # Taint rule: import can raise, never lower.
                    existing.sensitivity = _max_sensitivity(
                        existing.sensitivity, node_data.get("sensitivity")
                    )
                    stats["nodes_ingested"] += 1
                key_to_id[tuple(key)] = existing.id
            except Exception as e:
                stats["nodes_skipped"] += 1
                logger.warning(f"Bundle node import failed for {key}: {e}")

        for edge_data in graph.get("edges", []):
            try:
                src_key = tuple(edge_data.get("source_key") or [])
                tgt_key = tuple(edge_data.get("target_key") or [])
                src_id = key_to_id.get(src_key)
                tgt_id = key_to_id.get(tgt_key)
                if not src_id or not tgt_id:
                    stats["edges_skipped_unresolved"] += 1
                    continue
                rel = edge_data.get("relationship_type") or "related_to"
                dup = db.query(GraphEdge).filter(
                    GraphEdge.workspace_id == workspace_id,
                    GraphEdge.source_node_id == src_id,
                    GraphEdge.target_node_id == tgt_id,
                    GraphEdge.relationship_type == rel,
                ).first()
                if dup:
                    continue
                db.add(GraphEdge(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    source_node_id=src_id,
                    target_node_id=tgt_id,
                    relationship_type=rel,
                    weight=edge_data.get("weight", 1.0),
                    properties=dict(edge_data.get("properties") or {}),
                ))
                stats["edges_ingested"] += 1
            except Exception as e:
                logger.warning(f"Bundle edge import failed: {e}")

        db.commit()
        return stats

    async def _apply_texts_section(
        self,
        db: Session,
        texts: Dict[str, Any],
        workspace_id: str,
        tenant_id: Optional[str],
        memory_handler,
    ) -> Dict[str, int]:
        """Import knowledge documents (SQL upsert) + business facts (LanceDB)."""
        from core.models import KnowledgeDocument

        stats = {"knowledge_ingested": 0, "knowledge_skipped": 0,
                 "facts_ingested": 0, "facts_skipped": 0}

        for kd in texts.get("knowledge_documents", []):
            try:
                content = kd.get("content") or ""
                if not content:
                    stats["knowledge_skipped"] += 1
                    continue
                dup = db.query(KnowledgeDocument).filter(
                    (KnowledgeDocument.workspace_id == workspace_id)
                    | (KnowledgeDocument.workspace_id.is_(None)),
                    KnowledgeDocument.content == content,
                ).first()
                if dup is not None:
                    stats["knowledge_skipped"] += 1
                    continue
                db.add(KnowledgeDocument(
                    tenant_id=tenant_id or "default",
                    workspace_id=workspace_id,
                    title=kd.get("title") or "",
                    content=content,
                    doc_type=kd.get("doc_type", "text"),
                    sensitivity=kd.get("sensitivity", "internal"),
                ))
                stats["knowledge_ingested"] += 1
            except Exception as e:
                stats["knowledge_skipped"] += 1
                logger.warning(f"Bundle knowledge doc import failed: {e}")
        db.commit()

        facts = texts.get("business_facts", [])
        if facts and memory_handler is not None:
            for fact in facts:
                try:
                    fact_text = fact.get("text") or ""
                    if not fact_text:
                        stats["facts_skipped"] += 1
                        continue
                    # Deterministic doc id → idempotent import.
                    fact_id = fact.get("fact_id") or hashlib.sha256(
                        fact_text.encode("utf-8")).hexdigest()[:32]
                    doc_id = f"orgbundle:{fact_id}"
                    await asyncio.to_thread(
                        memory_handler.add_document,
                        table_name="business_facts",
                        text=fact_text,
                        source="org_data_bundle",
                        metadata=dict(fact.get("metadata") or {}),
                        user_id="org_import",
                        doc_id=doc_id,
                        skip_ai_triggers=True,
                    )
                    stats["facts_ingested"] += 1
                except Exception as e:
                    stats["facts_skipped"] += 1
                    logger.warning(f"Bundle fact import failed: {e}")
        elif facts:
            stats["facts_skipped"] += len(facts)

        return stats
