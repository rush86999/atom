"""
Ontology layer for Atom (gap analysis remediation A1-A9, B3).

Pragmatic RDFS-style semantics over the existing Postgres graph — no triple
store, no OWL reasoner:

- EntityTypeDefinition.parent_type  → rdfs:subClassOf (class hierarchy)
- EntityTypeDefinition.aliases      → SKOS altLabel (type-label resolution)
- RelationTypeDefinition            → rdf:Property + rdfs:domain/range
  (legal source→relation→target triples for schema-constrained extraction
  and write-time validation — the SHACL role)
- to_jsonld()                       → RDF interchange (JSON-LD 1.1 export)

Enforcement mode: ATOM_ONTOLOGY_ENFORCEMENT = warn (default) | strict.
warn  — violating edges are written with properties.ontology_violation set.
strict — violating edges are rejected at write time.
"""

from core.ontology.ontology_service import (
    OntologyService,
    get_ontology_service,
    enforcement_mode,
)
from core.ontology.chunker import chunk_text, Chunk

__all__ = [
    "OntologyService",
    "get_ontology_service",
    "enforcement_mode",
    "chunk_text",
    "Chunk",
]
