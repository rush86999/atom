"""
GraphRAG Engine - Enhanced with LLM-powered extraction
Hierarchical Knowledge Graph with Global and Local Search (Microsoft GraphRAG-equivalent)
All data is user-specific. Integrates with Atom's memory system and BYOK.
"""

import logging
import os
import json
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)

# ==================== IMPORTS FOR ENHANCED FEATURES ====================

# BYOK Integration
try:
    from core.byok_endpoints import get_byok_manager
    BYOK_AVAILABLE = True
except ImportError:
    get_byok_manager = None
    BYOK_AVAILABLE = False

# OpenAI for LLM extraction
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available for GraphRAG LLM extraction")

# NetworkX for Leiden community detection
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logger.warning("NetworkX not available for Leiden community detection")

# ==================== CONFIGURATION ====================

GRAPHRAG_LLM_ENABLED = os.getenv("GRAPHRAG_LLM_ENABLED", "true").lower() == "true"
GRAPHRAG_LLM_PROVIDER = os.getenv("GRAPHRAG_LLM_PROVIDER", "openai")
GRAPHRAG_LLM_MODEL = os.getenv("GRAPHRAG_LLM_MODEL", "gpt-4o-mini")

# ==================== DATA CLASSES ====================

@dataclass
class Entity:
    """Named entity in the knowledge graph"""
    id: str
    name: str
    entity_type: str
    workspace_id: str
    user_id: Optional[str] = None
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
    workspace_id: str
    user_id: Optional[str] = None
    description: str = ""
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Community:
    """Hierarchical community of related entities"""
    id: str
    level: int
    entity_ids: List[str]
    workspace_id: str
    user_id: Optional[str] = None
    summary: str = ""
    keywords: List[str] = field(default_factory=list)


class GraphRAGEngine:
    """
    Enhanced GraphRAG engine with LLM-powered extraction and Leiden communities.
    Matches Microsoft GraphRAG quality while maintaining real-time ingestion.
    All data is workspace-specific for multi-tenant support.
    """
    
    def __init__(self):
        self._entities: Dict[str, Dict[str, Entity]] = defaultdict(dict)
        self._relationships: Dict[str, Dict[str, Relationship]] = defaultdict(dict)
        self._communities: Dict[str, Dict[str, Community]] = defaultdict(dict)
        self._adjacency: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self._community_summary_cache: Dict[str, str] = {}  # Cache LLM summaries
        
        # Initialize LLM client via BYOK
        self._llm_client = None
        self._byok_manager = None
        self._initialize_llm_client()
    
    def _initialize_llm_client(self):
        """Initialize LLM client using BYOK system"""
        if not GRAPHRAG_LLM_ENABLED:
            logger.info("GraphRAG LLM extraction disabled via config")
            return
        
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI not available, falling back to pattern-based extraction")
            return
        
        try:
            # Get API key from BYOK manager
            if BYOK_AVAILABLE and get_byok_manager:
                self._byok_manager = get_byok_manager()
                api_key = self._byok_manager.get_api_key(GRAPHRAG_LLM_PROVIDER)
            else:
                api_key = os.getenv("OPENAI_API_KEY")
            
            if api_key:
                self._llm_client = OpenAI(api_key=api_key)
                logger.info(f"GraphRAG LLM client initialized with BYOK ({GRAPHRAG_LLM_PROVIDER})")
            else:
                logger.warning("No API key available for GraphRAG LLM extraction")
        except Exception as e:
            logger.error(f"Failed to initialize GraphRAG LLM client: {e}")
    
    def _is_llm_available(self) -> bool:
        """Check if LLM extraction is available"""
        return GRAPHRAG_LLM_ENABLED and self._llm_client is not None

    # ==================== LLM-POWERED EXTRACTION ====================

    def _llm_extract_entities_and_relationships(
        self, text: str, doc_id: str, source: str, workspace_id: str, user_id: Optional[str] = None
    ) -> tuple[List[Entity], List[Relationship]]:
        """Extract entities and relationships using LLM (Microsoft GraphRAG style)"""
        
        prompt = f"""Analyze the following text and extract:
1. Named entities (people, projects, tasks, documents, meetings, organizations, topics)
2. Relationships between entities

Text:
\"\"\"
{text[:4000]}
\"\"\"

Respond with valid JSON only:
{{
  "entities": [
    {{"name": "entity name", "type": "person|project|task|document|meeting|organization|topic", "description": "brief description"}}
  ],
  "relationships": [
    {{"from": "entity1 name", "to": "entity2 name", "type": "works_on|manages|collaborates_with|discusses|owns|part_of|related_to", "description": "relationship description"}}
  ]
}}"""

        try:
            response = self._llm_client.chat.completions.create(
                model=GRAPHRAG_LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert at extracting knowledge graph entities and relationships from text. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            data = json.loads(content)
            
            # Build Entity objects
            entities = []
            entity_name_to_id = {}
            for e_data in data.get("entities", []):
                entity_id = f"{e_data['type']}_{uuid.uuid4().hex[:8]}"
                entity = Entity(
                    id=entity_id,
                    name=e_data["name"],
                    entity_type=e_data.get("type", "unknown"),
                    workspace_id=workspace_id,
                    user_id=user_id,
                    description=e_data.get("description", ""),
                    properties={"source": source, "doc_id": doc_id, "llm_extracted": True}
                )
                entities.append(entity)
                entity_name_to_id[e_data["name"].lower()] = entity_id
            
            # Build Relationship objects
            relationships = []
            for r_data in data.get("relationships", []):
                from_name = r_data.get("from", "").lower()
                to_name = r_data.get("to", "").lower()
                
                from_id = entity_name_to_id.get(from_name)
                to_id = entity_name_to_id.get(to_name)
                
                if from_id and to_id:
                    rel = Relationship(
                        id=f"rel_{uuid.uuid4().hex[:8]}",
                        from_entity=from_id,
                        to_entity=to_id,
                        rel_type=r_data.get("type", "related_to"),
                        workspace_id=workspace_id,
                        user_id=user_id,
                        description=r_data.get("description", f"{from_name} {r_data.get('type', 'related_to')} {to_name}"),
                        properties={"llm_extracted": True}
                    )
                    relationships.append(rel)
            
            logger.info(f"LLM extracted {len(entities)} entities and {len(relationships)} relationships")
            return entities, relationships
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}, falling back to pattern-based")
            return [], []

    # ==================== PATTERN-BASED FALLBACK ====================

    def _pattern_extract_entities(self, text: str, doc_id: str, source: str, workspace_id: str, user_id: Optional[str] = None) -> List[Entity]:
        """Fallback pattern-based entity extraction"""
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
                        workspace_id=workspace_id,
                        user_id=user_id,
                        description=context,
                        properties={"source": source, "doc_id": doc_id, "llm_extracted": False}
                    ))
        
        # Extract capitalized proper nouns as potential entities
        for word in text.split():
            if len(word) > 2 and word[0].isupper() and word.isalpha():
                entities.append(Entity(
                    id=f"noun_{word.lower()}_{uuid.uuid4().hex[:4]}",
                    name=word,
                    entity_type="noun",
                    workspace_id=workspace_id,
                    user_id=user_id,
                    properties={"source": source, "llm_extracted": False}
                ))
        
        return entities[:20]
    
    def _pattern_extract_relationships(self, text: str, entities: List[Entity], workspace_id: str, user_id: Optional[str] = None) -> List[Relationship]:
        """Fallback pattern-based relationship extraction"""
        relationships = []
        
        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                if e1.name in text and e2.name in text:
                    relationships.append(Relationship(
                        id=f"rel_{uuid.uuid4().hex[:8]}",
                        from_entity=e1.id,
                        to_entity=e2.id,
                        rel_type="related_to",
                        workspace_id=workspace_id,
                        user_id=user_id,
                        description=f"{e1.name} is related to {e2.name}",
                        properties={"llm_extracted": False}
                    ))
        
        return relationships[:50]

    # ==================== UNIFIED EXTRACTION ====================

    def _extract_entities(self, text: str, doc_id: str, source: str, workspace_id: str, user_id: Optional[str] = None) -> List[Entity]:
        """Extract entities - tries LLM first, falls back to pattern-based"""
        if self._is_llm_available():
            entities, _ = self._llm_extract_entities_and_relationships(text, doc_id, source, workspace_id, user_id)
            if entities:
                return entities
        
        return self._pattern_extract_entities(text, doc_id, source, workspace_id, user_id)
    
    def _extract_relationships(self, text: str, entities: List[Entity], workspace_id: str, user_id: Optional[str] = None) -> List[Relationship]:
        """Extract relationships - for LLM mode, this is a no-op since LLM extracts both together"""
        # When LLM is used, relationships are extracted together with entities
        # This method is for pattern-based fallback
        if not self._is_llm_available() or not entities or not entities[0].properties.get("llm_extracted"):
            return self._pattern_extract_relationships(text, entities, workspace_id, user_id)
        return []

    # ==================== STRUCTURED INGESTION ====================

    def add_entities_and_relationships(self, workspace_id: str, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]], user_id: Optional[str] = None) -> Dict[str, int]:
        """Ingest pre-extracted structured entities and relationships from an LLM."""
        entity_count = 0
        rel_count = 0

        for e_data in entities:
            props = e_data.get("properties", {})
            entity = Entity(
                id=e_data["id"],
                name=props.get("name", e_data["id"]),
                entity_type=e_data.get("type", "unknown"),
                workspace_id=workspace_id,
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
                workspace_id=workspace_id,
                user_id=user_id,
                description=r_data.get("properties", {}).get("description", f"{r_data['from']} {r_data['type']} {r_data['to']}"),
                properties=r_data.get("properties", {})
            )
            self.add_relationship(rel)
            rel_count += 1

        return {"entities": entity_count, "relationships": rel_count}

    # ==================== INDEXING ====================
    
    def add_entity(self, entity: Entity) -> str:
        """Add entity to workspace graph"""
        self._entities[entity.workspace_id][entity.id] = entity
        return entity.id
    
    def add_relationship(self, rel: Relationship) -> str:
        """Add relationship to workspace graph"""
        self._relationships[rel.workspace_id][rel.id] = rel
        self._adjacency[rel.workspace_id][rel.from_entity].add(rel.to_entity)
        self._adjacency[rel.workspace_id][rel.to_entity].add(rel.from_entity)
        return rel.id
    
    def ingest_document(self, workspace_id: str, doc_id: str, text: str, source: str = "unknown", user_id: Optional[str] = None) -> Dict[str, int]:
        """Ingest document for a specific workspace using LLM extraction"""
        
        # Use LLM extraction which gets both entities and relationships together
        if self._is_llm_available():
            entities, relationships = self._llm_extract_entities_and_relationships(
                text, doc_id, source, workspace_id, user_id
            )
            if not entities:
                # Fallback if LLM failed
                entities = self._pattern_extract_entities(text, doc_id, source, workspace_id, user_id)
                relationships = self._pattern_extract_relationships(text, entities, workspace_id, user_id)
        else:
            entities = self._pattern_extract_entities(text, doc_id, source, workspace_id, user_id)
            relationships = self._pattern_extract_relationships(text, entities, workspace_id, user_id)
        
        for entity in entities:
            self.add_entity(entity)
        for rel in relationships:
            self.add_relationship(rel)
        
        return {"entities": len(entities), "relationships": len(relationships), "workspace_id": workspace_id, "llm_used": self._is_llm_available()}

    # ==================== LEIDEN COMMUNITY DETECTION ====================
    
    def build_communities(self, workspace_id: str, min_community_size: int = 2, resolution: float = 1.0) -> int:
        """Build communities using Leiden algorithm (NetworkX) or fallback to BFS"""
        
        workspace_entities = self._entities.get(workspace_id, {})
        workspace_adjacency = self._adjacency.get(workspace_id, {})
        
        if not workspace_entities:
            return 0
        
        # Try Leiden via NetworkX
        if NETWORKX_AVAILABLE:
            return self._build_communities_leiden(workspace_id, min_community_size, resolution)
        else:
            return self._build_communities_bfs(workspace_id, min_community_size)
    
    def _build_communities_leiden(self, workspace_id: str, min_community_size: int, resolution: float) -> int:
        """Build communities using Leiden/Louvain algorithm"""
        workspace_entities = self._entities.get(workspace_id, {})
        workspace_adjacency = self._adjacency.get(workspace_id, {})
        
        # Build NetworkX graph
        G = nx.Graph()
        for entity_id in workspace_entities:
            G.add_node(entity_id)
        
        for entity_id, neighbors in workspace_adjacency.items():
            for neighbor in neighbors:
                if entity_id in workspace_entities and neighbor in workspace_entities:
                    G.add_edge(entity_id, neighbor)
        
        if G.number_of_nodes() == 0:
            return 0
        
        # Run Louvain community detection (similar to Leiden, available in NetworkX)
        try:
            from networkx.algorithms.community import louvain_communities
            communities_list = louvain_communities(G, resolution=resolution, seed=42)
        except ImportError:
            # Fallback to basic connected components
            communities_list = list(nx.connected_components(G))
        
        # Create Community objects
        community_count = 0
        for community_set in communities_list:
            if len(community_set) >= min_community_size:
                community_id = f"community_{workspace_id}_{community_count}"
                entity_ids = list(community_set)
                
                # Generate summary using LLM or fallback
                summary = self._generate_community_summary(entity_ids, workspace_id)
                keywords = self._extract_community_keywords(entity_ids, workspace_id)
                
                community = Community(
                    id=community_id,
                    level=0,
                    entity_ids=entity_ids,
                    workspace_id=workspace_id,
                    summary=summary,
                    keywords=keywords
                )
                self._communities[workspace_id][community_id] = community
                
                # Update entity community assignments
                for eid in entity_ids:
                    if eid in workspace_entities:
                        workspace_entities[eid].community_id = community_id
                
                community_count += 1
        
        logger.info(f"Built {community_count} communities for workspace {workspace_id} using Louvain")
        return community_count
    
    def _build_communities_bfs(self, workspace_id: str, min_community_size: int) -> int:
        """Fallback BFS-based community detection"""
        visited = set()
        community_count = 0
        workspace_entities = self._entities.get(workspace_id, {})
        workspace_adjacency = self._adjacency.get(workspace_id, {})
        
        for entity_id in workspace_entities:
            if entity_id in visited:
                continue
            
            component = self._bfs_component(entity_id, visited, workspace_adjacency)
            
            if len(component) >= min_community_size:
                community_id = f"community_{workspace_id}_{community_count}"
                community = Community(
                    id=community_id,
                    level=0,
                    entity_ids=list(component),
                    workspace_id=workspace_id,
                    summary=self._generate_community_summary(list(component), workspace_id),
                    keywords=self._extract_community_keywords(list(component), workspace_id)
                )
                self._communities[workspace_id][community_id] = community
                
                for eid in component:
                    if eid in workspace_entities:
                        workspace_entities[eid].community_id = community_id
                
                community_count += 1
        
        logger.info(f"Built {community_count} communities for workspace {workspace_id} using BFS")
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

    # ==================== LLM-POWERED COMMUNITY SUMMARIES ====================
    
    def _generate_community_summary(self, entity_ids: List[str], workspace_id: str) -> str:
        """Generate community summary using LLM or fallback to keyword-based"""
        
        # Check cache first
        cache_key = f"{workspace_id}_{'_'.join(sorted(entity_ids[:5]))}"
        if cache_key in self._community_summary_cache:
            return self._community_summary_cache[cache_key]
        
        workspace_entities = self._entities.get(workspace_id, {})
        entities = [workspace_entities[eid] for eid in entity_ids if eid in workspace_entities]
        
        if not entities:
            return "Empty community"
        
        # Try LLM summarization
        if self._is_llm_available() and len(entities) >= 2:
            try:
                entity_descriptions = "\n".join([
                    f"- {e.name} ({e.entity_type}): {e.description}"
                    for e in entities[:15]
                ])
                
                prompt = f"""Summarize this group of related entities in 1-2 sentences. Focus on what connects them and their main theme.

Entities:
{entity_descriptions}

Summary:"""
                
                response = self._llm_client.chat.completions.create(
                    model=GRAPHRAG_LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a knowledge graph summarizer. Be concise."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=150
                )
                
                summary = response.choices[0].message.content.strip()
                self._community_summary_cache[cache_key] = summary
                return summary
                
            except Exception as e:
                logger.warning(f"LLM community summary failed: {e}")
        
        # Fallback: keyword-based summary
        types = defaultdict(list)
        for e in entities:
            types[e.entity_type].append(e.name)
        
        summary = "; ".join([f"{t}: {', '.join(n[:5])}" for t, n in types.items()])
        self._community_summary_cache[cache_key] = summary
        return summary
    
    def _extract_community_keywords(self, entity_ids: List[str], workspace_id: str) -> List[str]:
        """Extract keywords from community entities"""
        workspace_entities = self._entities.get(workspace_id, {})
        return list(set([workspace_entities[eid].name for eid in entity_ids if eid in workspace_entities]))[:10]

    # ==================== MAP-REDUCE GLOBAL SEARCH ====================
    
    def global_search(self, workspace_id: str, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Global Search using map-reduce over community summaries (Microsoft GraphRAG style)"""
        
        workspace_communities = self._communities.get(workspace_id, {})
        
        if not workspace_communities:
            return {
                "workspace_id": workspace_id, "query": query, "mode": "global",
                "communities_found": 0, "summaries": [],
                "answer": "No communities found. Try ingesting more documents."
            }
        
        # STAGE 1: Score and select relevant communities
        query_lower = query.lower()
        scored = []
        for community in workspace_communities.values():
            score = sum(2 for kw in community.keywords if kw.lower() in query_lower or query_lower in kw.lower())
            score += sum(1 for word in query_lower.split() if word in community.summary.lower())
            if score > 0:
                scored.append((community, score))
        
        if not scored:
            # Return all communities if no keyword matches
            scored = [(c, 0) for c in workspace_communities.values()]
        
        scored.sort(key=lambda x: x[1], reverse=True)
        top_communities = [c for c, _ in scored[:top_k]]
        summaries = [c.summary for c in top_communities]
        
        # STAGE 2: Map-reduce synthesis using LLM (if available)
        if self._is_llm_available() and summaries:
            try:
                context = "\n".join([f"Community {i+1}: {s}" for i, s in enumerate(summaries)])
                
                prompt = f"""Based on the following knowledge graph community summaries, answer the question.

Question: {query}

Community Context:
{context}

Provide a comprehensive answer based on the available information:"""
                
                response = self._llm_client.chat.completions.create(
                    model=GRAPHRAG_LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a knowledge synthesis assistant. Answer based only on the provided context."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                
                answer = response.choices[0].message.content.strip()
                
            except Exception as e:
                logger.warning(f"LLM global search failed: {e}")
                answer = " | ".join(summaries) if summaries else "No relevant information found"
        else:
            answer = " | ".join(summaries) if summaries else "No relevant communities found"
        
        return {
            "workspace_id": workspace_id, "query": query, "mode": "global",
            "communities_found": len(top_communities),
            "summaries": summaries,
            "answer": answer,
            "llm_used": self._is_llm_available()
        }

    # ==================== LOCAL SEARCH ====================
    
    def local_search(self, workspace_id: str, query: str, entity_name: str = None, depth: int = 2) -> Dict[str, Any]:
        """Local Search for workspace: entity-specific reasoning"""
        workspace_entities = self._entities.get(workspace_id, {})
        workspace_adjacency = self._adjacency.get(workspace_id, {})
        workspace_relationships = self._relationships.get(workspace_id, {})
        
        start_entity = None
        search_term = entity_name or query.lower()
        
        for e in workspace_entities.values():
            if search_term.lower() in e.name.lower() or e.name.lower() in search_term.lower():
                start_entity = e
                break
        
        if not start_entity:
            return {"workspace_id": workspace_id, "query": query, "mode": "local", "error": "No matching entity", "entities_found": 0}
        
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
                
                for neighbor_id in workspace_adjacency.get(eid, set()):
                    if neighbor_id not in visited and neighbor_id in workspace_entities:
                        next_frontier.add(neighbor_id)
                        all_entities.append(workspace_entities[neighbor_id])
                        
                        for rel in workspace_relationships.values():
                            if (rel.from_entity == eid and rel.to_entity == neighbor_id) or \
                               (rel.to_entity == eid and rel.from_entity == neighbor_id):
                                all_rels.append(rel)
            frontier = next_frontier
        
        return {
            "workspace_id": workspace_id, "query": query, "mode": "local",
            "start_entity": start_entity.name,
            "entities_found": len(all_entities),
            "relationships_found": len(all_rels),
            "entities": [{"id": e.id, "name": e.name, "type": e.entity_type, "description": e.description} for e in all_entities[:10]],
            "relationships": [{"from": r.from_entity, "to": r.to_entity, "type": r.rel_type, "description": r.description} for r in all_rels[:10]]
        }

    # ==================== UNIFIED QUERY ====================
    
    def query(self, workspace_id: str, query: str, mode: str = "auto") -> Dict[str, Any]:
        """Unified query interface for a workspace"""
        if mode == "auto":
            holistic = ["overview", "themes", "main", "all", "summary", "what are", "how do", "why"]
            mode = "global" if any(kw in query.lower() for kw in holistic) else "local"
        
        return self.global_search(workspace_id, query) if mode == "global" else self.local_search(workspace_id, query)

    # ==================== AI NODE INTEGRATION ====================
    
    def get_context_for_ai(self, workspace_id: str, query: str) -> str:
        """Get relevant context for AI nodes/chat - main integration point"""
        result = self.query(workspace_id, query)
        
        if result.get("mode") == "global":
            return f"Context from knowledge graph: {result.get('answer', '')}"
        else:
            entities = result.get("entities", [])
            entity_str = ", ".join([f"{e['name']} ({e['type']})" for e in entities[:5]])
            return f"Relevant entities: {entity_str}" if entities else ""
    
    def get_stats(self, workspace_id: str = None) -> Dict[str, Any]:
        """Get stats, optionally for a specific workspace"""
        if workspace_id:
            return {
                "entities": len(self._entities.get(workspace_id, {})),
                "relationships": len(self._relationships.get(workspace_id, {})),
                "communities": len(self._communities.get(workspace_id, {})),
                "llm_enabled": self._is_llm_available()
            }
        return {
            "total_workspaces": len(self._entities),
            "total_entities": sum(len(e) for e in self._entities.values()),
            "total_relationships": sum(len(r) for r in self._relationships.values()),
            "total_communities": sum(len(c) for c in self._communities.values()),
            "llm_enabled": self._is_llm_available()
        }


# Global instance
graphrag_engine = GraphRAGEngine()

def get_graphrag_context(workspace_id: str, query: str) -> str:
    """Helper function for AI nodes to get GraphRAG context"""
    return graphrag_engine.get_context_for_ai(workspace_id, query)
