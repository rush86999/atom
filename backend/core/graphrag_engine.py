"""
GraphRAG Engine - Phase 42
Hierarchical Knowledge Graph with Global and Local Search
All data is user-specific. Integrates with Atom's memory system throughout.
"""

import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)

@dataclass
class Entity:
    """Named entity in the knowledge graph"""
    id: str
    name: str
    entity_type: str
    user_id: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    community_id: Optional[str] = None

@dataclass
class Relationship:
    """Edge between entities"""
    id: str
    from_entity: str
    to_entity: str
    rel_type: str
    user_id: str
    description: str = ""
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Community:
    """Hierarchical community of related entities"""
    id: str
    level: int
    entity_ids: List[str]
    user_id: str
    summary: str = ""
    keywords: List[str] = field(default_factory=list)

class GraphRAGEngine:
    """
    GraphRAG-style engine with hierarchical communities.
    All data is user-specific for multi-tenant support.
    Designed for integration with Atom's memory and AI nodes.
    """
    
    def __init__(self):
        self._entities: Dict[str, Dict[str, Entity]] = defaultdict(dict)
        self._relationships: Dict[str, Dict[str, Relationship]] = defaultdict(dict)
        self._communities: Dict[str, Dict[str, Community]] = defaultdict(dict)
        self._adjacency: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))  # user_id -> {entity_id -> neighbor_ids}

    # ==================== STRUCTURED INGESTION ====================

    def add_entities_and_relationships(self, user_id: str, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Ingest pre-extracted structured entities and relationships from an LLM.
        """
        entity_count = 0
        rel_count = 0

        for e_data in entities:
            props = e_data.get("properties", {})
            entity = Entity(
                id=e_data["id"],
                name=props.get("name", e_data["id"]),
                entity_type=e_data.get("type", "unknown"),
                user_id=user_id,
                description=props.get("description", ""),
                properties=props
            )
            self.add_entity(entity)
            entity_count += 1

        for r_data in relationships:
            rel = Relationship(
                id=f"rel_{uuid.uuid4().hex[:8]}",
                from_entity=r_data["from"],
                to_entity=r_data["to"],
                rel_type=r_data["type"],
                user_id=user_id,
                description=r_data.get("properties", {}).get("description", f"{r_data['from']} {r_data['type']} {r_data['to']}"),
                properties=r_data.get("properties", {})
            )
            self.add_relationship(rel)
            rel_count += 1

        return {"entities": entity_count, "relationships": rel_count}
    # ==================== INDEXING (User-Specific) ====================
    
    def add_entity(self, entity: Entity) -> str:
        """Add entity to user's graph"""
        self._entities[entity.user_id][entity.id] = entity
        return entity.id
    
    def add_relationship(self, rel: Relationship) -> str:
        """Add relationship to user's graph"""
        self._relationships[rel.user_id][rel.id] = rel
        self._adjacency[rel.user_id][rel.from_entity].add(rel.to_entity)
        self._adjacency[rel.user_id][rel.to_entity].add(rel.from_entity)
        return rel.id
    
    def ingest_document(self, user_id: str, doc_id: str, text: str, source: str = "unknown") -> Dict[str, int]:
        """Ingest document for a specific user"""
        entities = self._extract_entities(text, doc_id, source, user_id)
        relationships = self._extract_relationships(text, entities, user_id)
        
        for entity in entities:
            self.add_entity(entity)
        for rel in relationships:
            self.add_relationship(rel)
        
        return {"entities": len(entities), "relationships": len(relationships), "user_id": user_id}
    
    def _extract_entities(self, text: str, doc_id: str, source: str, user_id: str) -> List[Entity]:
        """Extract entities from text"""
        entities = []
        patterns = {
            "project": ["project", "initiative", "program"],
            "person": ["@", "contact", "team member", "stakeholder", "manager", "director", "executive", "vp", "ceo", "cto", "cfo"],
            "task": ["task", "todo", "action item"],
            "document": ["document", "file", "report"],
            "meeting": ["meeting", "call", "sync"],
        }
        
        text_lower = text.lower()
        
        for entity_type, keywords in patterns.items():
            for kw in keywords:
                if kw in text_lower:
                    idx = text_lower.find(kw)
                    context = text[max(0, idx-20):idx+50]
                    entities.append(Entity(
                        id=f"{entity_type}_{uuid.uuid4().hex[:8]}",
                        name=context[:30].strip(),
                        entity_type=entity_type,
                        user_id=user_id,
                        description=context,
                        properties={"source": source, "doc_id": doc_id}
                    ))
        
        # Extract capitalized proper nouns
        for word in text.split():
            if len(word) > 2 and word[0].isupper() and word.isalpha():
                entities.append(Entity(
                    id=f"noun_{word.lower()}_{uuid.uuid4().hex[:4]}",
                    name=word,
                    entity_type="noun",
                    user_id=user_id,
                    properties={"source": source}
                ))
        
        return entities[:20]
    
    def _extract_relationships(self, text: str, entities: List[Entity], user_id: str) -> List[Relationship]:
        """Extract relationships between entities"""
        relationships = []
        
        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                if e1.name in text and e2.name in text:
                    relationships.append(Relationship(
                        id=f"rel_{uuid.uuid4().hex[:8]}",
                        from_entity=e1.id,
                        to_entity=e2.id,
                        rel_type="related_to",
                        user_id=user_id,
                        description=f"{e1.name} is related to {e2.name}"
                    ))
        
        return relationships[:50]
    
    # ==================== COMMUNITY DETECTION (Per-User) ====================
    
    def build_communities(self, user_id: str, min_community_size: int = 2) -> int:
        """Build communities for a specific user"""
        visited = set()
        community_count = 0
        user_entities = self._entities.get(user_id, {})
        user_adjacency = self._adjacency.get(user_id, {})
        
        for entity_id in user_entities:
            if entity_id in visited:
                continue
            
            component = self._bfs_component(entity_id, visited, user_adjacency)
            
            if len(component) >= min_community_size:
                community = Community(
                    id=f"community_{user_id}_{community_count}",
                    level=0,
                    entity_ids=list(component),
                    user_id=user_id,
                    summary=self._generate_community_summary(component, user_id),
                    keywords=self._extract_community_keywords(component, user_id)
                )
                self._communities[user_id][community.id] = community
                
                for eid in component:
                    if eid in user_entities:
                        user_entities[eid].community_id = community.id
                
                community_count += 1
        
        logger.info(f"Built {community_count} communities for user {user_id}")
        return community_count
    
    def _bfs_component(self, start: str, visited: Set[str], adjacency: Dict[str, Set[str]]) -> Set[str]:
        """BFS to find connected component"""
        component = set()
        queue = [start]
        
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            
            for neighbor in adjacency.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        
        return component
    
    def _generate_community_summary(self, entity_ids: Set[str], user_id: str) -> str:
        user_entities = self._entities.get(user_id, {})
        entities = [user_entities[eid] for eid in entity_ids if eid in user_entities]
        types = defaultdict(list)
        
        for e in entities:
            types[e.entity_type].append(e.name)
        
        return "; ".join([f"{t}: {', '.join(n[:5])}" for t, n in types.items()])
    
    def _extract_community_keywords(self, entity_ids: Set[str], user_id: str) -> List[str]:
        user_entities = self._entities.get(user_id, {})
        return list(set([user_entities[eid].name for eid in entity_ids if eid in user_entities]))[:10]
    
    # ==================== GLOBAL SEARCH (Per-User) ====================
    
    def global_search(self, user_id: str, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Global Search for user: holistic questions using community summaries"""
        query_lower = query.lower()
        user_communities = self._communities.get(user_id, {})
        
        scored = []
        for community in user_communities.values():
            score = sum(2 for kw in community.keywords if kw.lower() in query_lower or query_lower in kw.lower())
            score += sum(1 for word in query_lower.split() if word in community.summary.lower())
            if score > 0:
                scored.append((community, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        summaries = [c.summary for c, _ in scored[:top_k]]
        
        return {
            "user_id": user_id, "query": query, "mode": "global",
            "communities_found": len(scored[:top_k]),
            "summaries": summaries,
            "answer": " | ".join(summaries) if summaries else "No relevant communities found"
        }
    
    # ==================== LOCAL SEARCH (Per-User) ====================
    
    def local_search(self, user_id: str, query: str, entity_name: str = None, depth: int = 2) -> Dict[str, Any]:
        """Local Search for user: entity-specific reasoning"""
        user_entities = self._entities.get(user_id, {})
        user_adjacency = self._adjacency.get(user_id, {})
        user_relationships = self._relationships.get(user_id, {})
        
        start_entity = None
        search_term = entity_name or query.lower()
        
        for e in user_entities.values():
            if search_term.lower() in e.name.lower() or e.name.lower() in search_term.lower():
                start_entity = e
                break
        
        if not start_entity:
            return {"user_id": user_id, "query": query, "mode": "local", "error": "No matching entity", "entities_found": 0}
        
        visited = set()
        frontier = {start_entity.id}
        all_entities = [start_entity]
        all_rels = []
        
        for _ in range(depth):
            next_frontier = set()
            for eid in frontier:
                if eid in visited:
                    continue
                visited.add(eid)
                
                for neighbor_id in user_adjacency.get(eid, set()):
                    if neighbor_id not in visited and neighbor_id in user_entities:
                        next_frontier.add(neighbor_id)
                        all_entities.append(user_entities[neighbor_id])
                        
                        for rel in user_relationships.values():
                            if (rel.from_entity == eid and rel.to_entity == neighbor_id) or \
                               (rel.to_entity == eid and rel.from_entity == neighbor_id):
                                all_rels.append(rel)
            frontier = next_frontier
        
        return {
            "user_id": user_id, "query": query, "mode": "local",
            "start_entity": start_entity.name,
            "entities_found": len(all_entities),
            "relationships_found": len(all_rels),
            "entities": [{"id": e.id, "name": e.name, "type": e.entity_type} for e in all_entities[:10]],
            "relationships": [{"from": r.from_entity, "to": r.to_entity, "type": r.rel_type} for r in all_rels[:10]]
        }
    
    # ==================== UNIFIED QUERY (Per-User) ====================
    
    def query(self, user_id: str, query: str, mode: str = "auto") -> Dict[str, Any]:
        """Unified query interface for a user"""
        if mode == "auto":
            holistic = ["overview", "themes", "main", "all", "summary", "what are"]
            mode = "global" if any(kw in query.lower() for kw in holistic) else "local"
        
        return self.global_search(user_id, query) if mode == "global" else self.local_search(user_id, query)
    
    # ==================== AI NODE INTEGRATION ====================
    
    def get_context_for_ai(self, user_id: str, query: str) -> str:
        """Get relevant context for AI nodes/chat - main integration point"""
        result = self.query(user_id, query)
        
        if result.get("mode") == "global":
            return f"Context from knowledge graph: {result.get('answer', '')}"
        else:
            entities = result.get("entities", [])
            entity_str = ", ".join([f"{e['name']} ({e['type']})" for e in entities[:5]])
            return f"Relevant entities: {entity_str}" if entities else ""
    
    def get_stats(self, user_id: str = None) -> Dict[str, int]:
        """Get stats, optionally for a specific user"""
        if user_id:
            return {
                "entities": len(self._entities.get(user_id, {})),
                "relationships": len(self._relationships.get(user_id, {})),
                "communities": len(self._communities.get(user_id, {}))
            }
        return {
            "total_users": len(self._entities),
            "total_entities": sum(len(e) for e in self._entities.values()),
            "total_relationships": sum(len(r) for r in self._relationships.values()),
            "total_communities": sum(len(c) for c in self._communities.values())
        }

# Global instance
graphrag_engine = GraphRAGEngine()

def get_graphrag_context(user_id: str, query: str) -> str:
    """Helper function for AI nodes to get GraphRAG context"""
    return graphrag_engine.get_context_for_ai(user_id, query)
