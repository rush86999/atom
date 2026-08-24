"""
Ontology Service — schema layer for the GraphRAG knowledge graph.

Closes gaps A1 (relation domain/range), A2 (subclass hierarchy), A4
(write-time validation), A5 (alias resolution), A6 seeds the hypothesis
lifecycle vocabulary, and A9 (JSON-LD export).

The service is deliberately fail-open at the infrastructure level: if the
ontology tables are unavailable the caller falls back to the legacy
hardcoded prompt lists, so extraction never breaks because of the schema
layer. Semantic enforcement is controlled by ATOM_ONTOLOGY_ENFORCEMENT.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60


def enforcement_mode() -> str:
    """warn (default): violations flagged in edge properties; strict: rejected."""
    return os.getenv("ATOM_ONTOLOGY_ENFORCEMENT", "warn").strip().lower()


# ============================================================================
# Seed ontology — derived from the legacy hardcoded extraction prompt
# (core/knowledge_extractor.py) plus the pattern-extractor types, now with
# RDFS-style hierarchy and SKOS-style aliases.
# ============================================================================

SEED_ENTITY_TYPES: List[Dict[str, Any]] = [
    # slug, parent, abstract (not offered to the LLM as extractable), aliases, fields
    {"slug": "Person", "parent": None, "abstract": False, "aliases": ["person", "contact", "user", "people"],
     "fields": "name, role, organization, is_stakeholder: bool"},
    {"slug": "Organization", "parent": None, "abstract": False, "aliases": ["organization", "org", "company", "organisation"],
     "fields": "name"},
    {"slug": "Project", "parent": None, "abstract": False, "aliases": ["project", "initiative"],
     "fields": "name, status"},
    {"slug": "Task", "parent": None, "abstract": False, "aliases": ["task", "todo", "action_item"],
     "fields": "description, status, owner"},
    {"slug": "File", "parent": None, "abstract": False, "aliases": ["file", "document", "attachment"],
     "fields": "filename, type"},
    {"slug": "Decision", "parent": None, "abstract": False, "aliases": ["decision"],
     "fields": "summary, context, date, impact_level"},
    {"slug": "BusinessRule", "parent": None, "abstract": False, "aliases": ["businessrule", "business_rule", "policy", "rule"],
     "fields": "description, type, value, applies_to"},
    {"slug": "Message", "parent": None, "abstract": True, "aliases": ["message", "email_message", "chat_message"],
     "fields": "channel, date"},
    {"slug": "Transaction", "parent": None, "abstract": True, "aliases": ["transaction"],
     "fields": "amount, currency, date, category"},
    {"slug": "Invoice", "parent": "Transaction", "abstract": False, "aliases": ["invoice", "bill"],
     "fields": "invoice_number, amount, recipient, status, due_date"},
    {"slug": "PurchaseOrder", "parent": "Transaction", "abstract": False, "aliases": ["purchaseorder", "purchase_order", "po"],
     "fields": "id, items, total_amount, vendor, shipping_address"},
    {"slug": "SalesOrder", "parent": "Transaction", "abstract": False, "aliases": ["salesorder", "sales_order", "order"],
     "fields": "id, order_number, total_amount, items"},
    {"slug": "Opportunity", "parent": None, "abstract": True, "aliases": ["opportunity"],
     "fields": "name, value, stage"},
    {"slug": "Deal", "parent": "Opportunity", "abstract": False, "aliases": ["deal"],
     "fields": "name, value, stage, health_score, external_id"},
    {"slug": "Lead", "parent": "Opportunity", "abstract": False, "aliases": ["lead", "prospect"],
     "fields": "name, company, email, score, external_id"},
    {"slug": "Quote", "parent": None, "abstract": False, "aliases": ["quote", "quotation"],
     "fields": "id, amount, items, terms, status: [requested, offered]"},
    {"slug": "Shipment", "parent": None, "abstract": False, "aliases": ["shipment", "delivery"],
     "fields": "tracking_number, carrier, status, estimated_delivery"},
    # Regex-pattern extractor types (graphrag_engine._pattern_extract_...)
    {"slug": "Pattern", "parent": None, "abstract": True, "aliases": ["pattern"], "fields": "value"},
    {"slug": "email", "parent": "Pattern", "abstract": True, "aliases": [], "fields": "address"},
    {"slug": "url", "parent": "Pattern", "abstract": True, "aliases": [], "fields": "url"},
    {"slug": "phone", "parent": "Pattern", "abstract": True, "aliases": [], "fields": "number"},
    {"slug": "date", "parent": "Pattern", "abstract": True, "aliases": [], "fields": "date"},
    {"slug": "currency", "parent": "Pattern", "abstract": True, "aliases": [], "fields": "amount"},
    {"slug": "file_path", "parent": "Pattern", "abstract": True, "aliases": [], "fields": "path"},
    {"slug": "ip_address", "parent": "Pattern", "abstract": True, "aliases": [], "fields": "address"},
    {"slug": "uuid", "parent": "Pattern", "abstract": True, "aliases": [], "fields": "value"},
]

SEED_RELATIONS: List[Dict[str, Any]] = [
    {"name": "PARTICIPATED_IN", "domain": ["Person"], "range": ["Decision", "Project", "Message"],
     "description": "Person took part in a decision/project/message thread"},
    {"name": "REFERENCE_TO", "domain": ["Message", "File", "Task"], "range": ["File", "Project"],
     "description": "A message/file/task references a file or project"},
    {"name": "OWNS", "domain": ["Person", "Organization"], "range": ["Project", "Task", "File", "Opportunity"],
     "description": "Ownership of a project/task/file/opportunity", "inverse_of": "OWNED_BY"},
    {"name": "STAKEHOLDER_OF", "domain": ["Person"], "range": ["Project", "Organization"],
     "description": "Person is a stakeholder of a project/organization"},
    {"name": "REPORTS_TO", "domain": ["Person"], "range": ["Person"],
     "description": "Organizational reporting line", "inverse_of": "REPORTS_TO"},
    {"name": "ASSIGNED_TO", "domain": ["Task"], "range": ["Person"],
     "description": "Task assigned to a person"},
    {"name": "DECIDED_ON", "domain": ["Person"], "range": ["Decision"],
     "description": "Person made a decision"},
    {"name": "PART_OF", "domain": ["Task", "File"], "range": ["Project", "Task"],
     "description": "Containment within a project or parent task"},
    {"name": "INTENT", "domain": ["Message"], "range": ["*"],
     "description": "Detected intent (payment_commitment, churn_threat, upsell_inquiry, "
                    "meeting_request, approval, request_quote, offer_quote, confirm_shipping, dispute_invoice)"},
    {"name": "UPDATES_STATUS", "domain": ["Shipment", "Quote"], "range": ["Deal", "SalesOrder"],
     "description": "A shipment/quote updates the status of a deal/order"},
    {"name": "LINKS_TO_EXTERNAL", "domain": ["*"], "range": ["*"],
     "description": "Entity maps to an external system ID (CRM/ERP)"},
    {"name": "RELATED_TO", "domain": ["*"], "range": ["*"],
     "description": "Generic fallback relation (previously the silent default)"},
]

VALID_VERIFICATION_STATES = ("proposed", "verified", "retired")


class ValidationResult:
    """Outcome of an edge validation against the ontology."""

    __slots__ = ("ok", "declared", "reason")

    def __init__(self, ok: bool, declared: bool, reason: str = ""):
        self.ok = ok
        self.declared = declared
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ValidationResult ok={self.ok} declared={self.declared} reason={self.reason!r}>"


class OntologyService:
    """Schema-constrained extraction + write-time validation + JSON-LD export."""

    def __init__(self, tenant_id: str = "default", session_factory=None):
        self.tenant_id = tenant_id or "default"
        self._session_factory = session_factory
        self._cache: Optional[Tuple[float, Dict[str, Any]]] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ util

    def _sessions(self):
        if self._session_factory is not None:
            return self._session_factory
        from core.database import get_db_session
        return get_db_session

    def _ensure_tables(self) -> bool:
        """Create ontology tables/columns if missing (dev + fresh installs).

        main_api_app runs Base.metadata.create_all at boot, but existing
        deployments upgrading in place need the ALTERs. Idempotent, guarded —
        failure just means the caller falls back to legacy behavior.
        """
        try:
            from core.database import engine
            from core.models import Base, EntityTypeDefinition, RelationTypeDefinition
            from sqlalchemy import inspect, text

            inspector = inspect(engine)
            existing = set(inspector.get_table_names())
            to_create = [
                t for t in (RelationTypeDefinition.__table__, EntityTypeDefinition.__table__,
                            )
                if t.name not in existing
            ]
            # GoalObjective lives in core.models too; create if missing.
            from core.models import GoalObjective
            if GoalObjective.__table__.name not in existing:
                to_create.append(GoalObjective.__table__)
            if to_create:
                Base.metadata.create_all(bind=engine, tables=to_create)

            # ALTER for new EntityTypeDefinition columns on existing tables.
            if EntityTypeDefinition.__table__.name in existing or to_create:
                cols = {c["name"] for c in inspector.get_columns(EntityTypeDefinition.__tablename__)}
                with engine.begin() as conn:
                    if "parent_type" not in cols:
                        conn.execute(text(
                            "ALTER TABLE entity_type_definitions ADD COLUMN parent_type VARCHAR(100)"))
                    if "aliases" not in cols:
                        conn.execute(text(
                            "ALTER TABLE entity_type_definitions ADD COLUMN aliases JSON"))
            return True
        except Exception as exc:  # pragma: no cover - infra-dependent
            logger.warning(f"Ontology table bootstrap skipped: {exc}")
            return False

    # ------------------------------------------------------------------ seed

    def ensure_seeded(self) -> Dict[str, int]:
        """Idempotently seed system entity + relation types. Returns counts."""
        self._ensure_tables()
        created_types = created_rels = 0
        try:
            from core.models import EntityTypeDefinition, RelationTypeDefinition
            with self._sessions()() as session:
                for seed in SEED_ENTITY_TYPES:
                    exists = session.query(EntityTypeDefinition).filter(
                        EntityTypeDefinition.tenant_id == self.tenant_id,
                        EntityTypeDefinition.slug == seed["slug"],
                        EntityTypeDefinition.is_system.is_(True),
                    ).first()
                    if exists:
                        continue
                    session.add(EntityTypeDefinition(
                        tenant_id=self.tenant_id,
                        slug=seed["slug"],
                        display_name=seed["slug"],
                        description=f"System ontology type (parent={seed['parent']})",
                        json_schema={
                            "type": "object",
                            "properties": {},
                            "x-atom-abstract": seed["abstract"],
                        },
                        parent_type=seed["parent"],
                        aliases=list(seed["aliases"]),
                        is_system=True,
                        metadata_json={"abstract": seed["abstract"], "fields": seed["fields"]},
                    ))
                    created_types += 1

                for rel in SEED_RELATIONS:
                    exists = session.query(RelationTypeDefinition).filter(
                        RelationTypeDefinition.tenant_id == self.tenant_id,
                        RelationTypeDefinition.name == rel["name"],
                        RelationTypeDefinition.is_system.is_(True),
                    ).first()
                    if exists:
                        continue
                    session.add(RelationTypeDefinition(
                        tenant_id=self.tenant_id,
                        name=rel["name"],
                        display_name=rel["name"].replace("_", " ").title(),
                        description=rel.get("description", ""),
                        domain_type=list(rel["domain"]),
                        range_type=list(rel["range"]),
                        inverse_of=rel.get("inverse_of"),
                        is_system=True,
                    ))
                    created_rels += 1
                session.commit()
        except Exception as exc:
            logger.warning(f"Ontology seeding skipped: {exc}")
        self._invalidate_cache()
        return {"entity_types_created": created_types, "relations_created": created_rels}

    # ----------------------------------------------------------------- schema

    def _invalidate_cache(self) -> None:
        with self._lock:
            self._cache = None

    def get_schema(self) -> Dict[str, Any]:
        """Full ontology schema: entity types (with hierarchy/aliases) + relations."""
        now = time.time()
        if self._cache and now - self._cache[0] < CACHE_TTL_SECONDS:
            return self._cache[1]
        schema = self._load_schema()
        with self._lock:
            self._cache = (now, schema)
        return schema

    def _load_schema(self) -> Dict[str, Any]:
        entity_types: List[Dict[str, Any]] = []
        relations: List[Dict[str, Any]] = []
        try:
            from core.models import EntityTypeDefinition, RelationTypeDefinition
            with self._sessions()() as session:
                for t in session.query(EntityTypeDefinition).filter(
                    EntityTypeDefinition.tenant_id == self.tenant_id,
                    EntityTypeDefinition.is_active.is_(True),
                ).all():
                    meta = t.metadata_json or {}
                    entity_types.append({
                        "slug": t.slug,
                        "display_name": t.display_name,
                        "description": t.description,
                        "parent_type": t.parent_type,
                        "aliases": list(t.aliases or []),
                        "abstract": bool(meta.get("abstract", False)),
                        "fields": meta.get("fields", ""),
                        "is_system": bool(t.is_system),
                        "json_schema": t.json_schema,
                    })
                for r in session.query(RelationTypeDefinition).filter(
                    RelationTypeDefinition.tenant_id == self.tenant_id,
                    RelationTypeDefinition.is_active.is_(True),
                ).all():
                    relations.append({
                        "name": r.name,
                        "display_name": r.display_name or r.name,
                        "description": r.description or "",
                        "domain": list(r.domain_type or ["*"]),
                        "range": list(r.range_type or ["*"]),
                        "inverse_of": r.inverse_of,
                        "cardinality": r.cardinality,
                    })
        except Exception as exc:
            logger.debug(f"Ontology schema load failed (fallback to seed): {exc}")
        if not entity_types and not relations:
            # DB unavailable → fall back to static seed so validation and
            # prompt generation still work (e.g. unit tests, degraded boot).
            entity_types = [
                {"slug": s["slug"], "display_name": s["slug"], "description": "",
                 "parent_type": s["parent"], "aliases": list(s["aliases"]),
                 "abstract": s["abstract"], "fields": s["fields"], "is_system": True,
                 "json_schema": None}
                for s in SEED_ENTITY_TYPES
            ]
            relations = [
                {"name": r["name"], "display_name": r["name"], "description": r.get("description", ""),
                 "domain": list(r["domain"]), "range": list(r["range"]),
                 "inverse_of": r.get("inverse_of"), "cardinality": "many_to_many"}
                for r in SEED_RELATIONS
            ]
        return {"entity_types": entity_types, "relations": relations}

    # ----------------------------------------------------- hierarchy helpers

    def _parents_map(self) -> Dict[str, Optional[str]]:
        return {t["slug"]: t.get("parent_type") for t in self.get_schema()["entity_types"]}

    def ancestors(self, type_slug: str) -> Set[str]:
        """Subclass closure: the type plus all its ancestors (rdfs:subClassOf*)."""
        parents = self._parents_map()
        seen: Set[str] = set()
        cur: Optional[str] = type_slug
        while cur and cur not in seen:
            seen.add(cur)
            cur = parents.get(cur)
        return seen

    def is_subtype(self, sub: str, sup: str) -> bool:
        return sup in self.ancestors(sub)

    def resolve_entity_type(self, raw: str) -> Optional[str]:
        """Resolve a free-text type label to a canonical slug (slug, alias,
        or display name; case-insensitive). Returns None when unknown."""
        if not raw:
            return None
        lowered = raw.strip().lower()
        for t in self.get_schema()["entity_types"]:
            if t["slug"].lower() == lowered or t["display_name"].lower() == lowered:
                return t["slug"]
            for alias in t["aliases"]:
                if alias.lower() == lowered:
                    return t["slug"]
        return None

    def aliases_for(self, type_slug: str) -> List[str]:
        for t in self.get_schema()["entity_types"]:
            if t["slug"].lower() == type_slug.lower():
                return [type_slug] + [a for a in t["aliases"]]
        return [type_slug]

    # ------------------------------------------------------------ validation

    @staticmethod
    def _type_allowed(actual: str, allowed: List[str], ancestors_of) -> bool:
        if "*" in allowed or not allowed:
            return True
        closure = ancestors_of(actual)
        return any(a in closure for a in allowed)

    def validate_relationship(
        self, source_type: str, relation: str, target_type: str
    ) -> ValidationResult:
        """Check a (source → relation → target) triple against the ontology.

        - Undeclared relation types pass (marked undeclared) so existing data
          flows are never bricked; the meta-agent surfaces them as suggestions
          to formalize.
        - Declared relations check domain/range with subclass closure.
        """
        rel_def = next(
            (r for r in self.get_schema()["relations"] if r["name"].upper() == (relation or "").upper()),
            None,
        )
        if rel_def is None:
            return ValidationResult(True, declared=False,
                                    reason=f"relation '{relation}' not declared in ontology")
        src = self.resolve_entity_type(source_type) or source_type
        tgt = self.resolve_entity_type(target_type) or target_type
        if not self._type_allowed(src, rel_def["domain"], self.ancestors):
            return ValidationResult(
                False, True,
                f"domain violation: {source_type} not in allowed domain {rel_def['domain']} for {relation}")
        if not self._type_allowed(tgt, rel_def["range"], self.ancestors):
            return ValidationResult(
                False, True,
                f"range violation: {target_type} not in allowed range {rel_def['range']} for {relation}")
        return ValidationResult(True, True)

    # -------------------------------------------------------- JSON-LD export

    def to_jsonld(self, include_graph: bool = False, workspace_id: str = "default") -> Dict[str, Any]:
        """Serialize the ontology (and optionally graph slices) as JSON-LD 1.1."""
        schema = self.get_schema()
        ns = "https://atom.local/ontology/"
        graph: List[Dict[str, Any]] = []
        for t in schema["entity_types"]:
            node: Dict[str, Any] = {
                "@id": ns + t["slug"],
                "@type": "rdfs:Class",
                "rdfs:label": t["display_name"],
            }
            if t.get("parent_type"):
                node["rdfs:subClassOf"] = {"@id": ns + t["parent_type"]}
            if t["aliases"]:
                node["skos:altLabel"] = t["aliases"]
            graph.append(node)
        for r in schema["relations"]:
            prop: Dict[str, Any] = {
                "@id": ns + r["name"],
                "@type": "rdf:Property",
                "rdfs:label": r["display_name"],
                "rdfs:comment": r["description"],
            }
            if r["domain"] and r["domain"] != ["*"]:
                prop["rdfs:domain"] = [{"@id": ns + d} for d in r["domain"]]
            if r["range"] and r["range"] != ["*"]:
                prop["rdfs:range"] = [{"@id": ns + rr} for rr in r["range"]]
            if r.get("inverse_of"):
                prop["owl:inverseOf"] = {"@id": ns + r["inverse_of"]}
            graph.append(prop)

        if include_graph:
            try:
                from core.models import GraphEdge, GraphNode
                with self._sessions()() as session:
                    for n in session.query(GraphNode).filter(
                        GraphNode.workspace_id == workspace_id
                    ).limit(500).all():
                        graph.append({
                            "@id": ns + "entity/" + str(n.id),
                            "@type": ns + (self.resolve_entity_type(n.type) or n.type),
                            "rdfs:label": n.name,
                        })
                    for e in session.query(GraphEdge).filter(
                        GraphEdge.workspace_id == workspace_id
                    ).limit(1000).all():
                        graph.append({
                            "@id": ns + "edge/" + str(e.id),
                            "@type": "rdf:Statement",
                            "rdf:subject": {"@id": ns + "entity/" + str(e.source_node_id)},
                            "rdf:predicate": {"@id": ns + e.relationship_type},
                            "rdf:object": {"@id": ns + "entity/" + str(e.target_node_id)},
                            "atom:verification": (e.properties or {}).get("verification", "untracked"),
                        })
            except Exception as exc:  # pragma: no cover - degraded export
                logger.warning(f"JSON-LD graph slice export skipped: {exc}")

        return {
            "@context": {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "owl": "http://www.w3.org/2002/07/owl#",
                "skos": "http://www.w3.org/2004/02/skos/core#",
                "atom": ns,
            },
            "@id": ns,
            "@type": "owl:Ontology",
            "rdfs:label": "Atom Knowledge Graph Ontology",
            "atom:exportedAt": datetime.now(timezone.utc).isoformat(),
            "@graph": graph,
        }

    # ------------------------------------------------- undeclared detection

    def undeclared_relations_in_use(self, workspace_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        """Relation types present in graph_edges but not declared in the ontology
        — candidates for formalization (GraphRAG auto-tuning role)."""
        try:
            from collections import Counter
            from core.models import GraphEdge
            declared = {r["name"].upper() for r in self.get_schema()["relations"]}
            with self._sessions()() as session:
                rows = session.query(
                    GraphEdge.relationship_type
                ).filter(GraphEdge.workspace_id == workspace_id).limit(limit * 10).all()
            counts = Counter((r[0] or "related_to").upper() for r in rows)
            return [
                {"name": name, "occurrences": count}
                for name, count in counts.most_common(limit)
                if name not in declared
            ]
        except Exception as exc:
            logger.debug(f"undeclared_relations_in_use failed: {exc}")
            return []


_services_by_tenant: Dict[str, OntologyService] = {}
_default_lock = threading.Lock()


def get_ontology_service(tenant_id: str = "default") -> OntologyService:
    """Per-tenant OntologyService cache.

    The previous process-global singleton bound itself to whichever tenant
    called first and ignored the tenant_id argument after that — in a
    multi-tenant deployment every tenant got tenant #1's schema (custom
    types, aliases), and the ?tenant_id= query param on the ontology routes
    was a silent no-op.
    """
    key = tenant_id or "default"
    with _default_lock:
        svc = _services_by_tenant.get(key)
        if svc is None:
            svc = OntologyService(tenant_id=key)
            _services_by_tenant[key] = svc
        return svc
