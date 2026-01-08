"""
Tests for Enhanced GraphRAG Engine
Tests LLM-powered extraction, Leiden communities, and map-reduce search.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json

# Import the module under test
from core.graphrag_engine import (
    GraphRAGEngine, Entity, Relationship, Community,
    graphrag_engine, get_graphrag_context
)


class TestGraphRAGEngineLLMExtraction:
    """Tests for LLM-powered entity/relationship extraction"""
    
    def setup_method(self):
        """Fresh engine for each test"""
        self.engine = GraphRAGEngine()
    
    @patch('core.graphrag_engine.OpenAI')
    def test_llm_extraction_returns_entities(self, mock_openai_class):
        """Test that LLM extraction parses entities correctly"""
        # Mock OpenAI response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "entities": [
                {"name": "Sarah", "type": "person", "description": "Marketing lead"},
                {"name": "Q4 Campaign", "type": "project", "description": "Marketing initiative"}
            ],
            "relationships": [
                {"from": "Sarah", "to": "Q4 Campaign", "type": "works_on", "description": "Sarah leads the campaign"}
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        # Create engine with mocked client
        engine = GraphRAGEngine()
        engine._llm_client = mock_client
        
        # Run extraction
        entities, relationships = engine._llm_extract_entities_and_relationships(
            text="Sarah is leading the Q4 Campaign.",
            doc_id="doc1",
            source="test",
            workspace_id="ws1",
            user_id="user1"
        )
        
        assert len(entities) == 2
        assert entities[0].name == "Sarah"
        assert entities[0].entity_type == "person"
        assert len(relationships) == 1
        assert relationships[0].rel_type == "works_on"
    
    def test_pattern_fallback_when_no_llm(self):
        """Test that pattern-based extraction works when LLM unavailable"""
        engine = GraphRAGEngine()
        engine._llm_client = None  # Force fallback
        
        entities = engine._pattern_extract_entities(
            text="The project meeting discussed the Q4 initiative with manager John.",
            doc_id="doc1",
            source="test",
            workspace_id="ws1"
        )
        
        # Should find "project", "meeting", "manager" patterns
        entity_types = [e.entity_type for e in entities]
        assert "project" in entity_types or "meeting" in entity_types
        assert len(entities) > 0


class TestGraphRAGEngineLeidenCommunities:
    """Tests for Leiden/Louvain community detection"""
    
    def setup_method(self):
        self.engine = GraphRAGEngine()
        self.engine._llm_client = None  # Disable LLM for unit tests
    
    def test_community_detection_creates_communities(self):
        """Test that community detection groups related entities"""
        workspace_id = "test_ws"
        
        # Add connected entities
        e1 = Entity(id="e1", name="Alice", entity_type="person", workspace_id=workspace_id)
        e2 = Entity(id="e2", name="Bob", entity_type="person", workspace_id=workspace_id)
        e3 = Entity(id="e3", name="Project X", entity_type="project", workspace_id=workspace_id)
        
        self.engine.add_entity(e1)
        self.engine.add_entity(e2)
        self.engine.add_entity(e3)
        
        # Add relationships
        r1 = Relationship(id="r1", from_entity="e1", to_entity="e2", rel_type="works_with", workspace_id=workspace_id)
        r2 = Relationship(id="r2", from_entity="e2", to_entity="e3", rel_type="works_on", workspace_id=workspace_id)
        
        self.engine.add_relationship(r1)
        self.engine.add_relationship(r2)
        
        # Build communities
        count = self.engine.build_communities(workspace_id, min_community_size=2)
        
        assert count >= 1
        communities = self.engine._communities.get(workspace_id, {})
        assert len(communities) >= 1
    
    def test_isolated_entity_not_in_community(self):
        """Test that isolated entities with < min_community_size are excluded"""
        workspace_id = "test_ws"
        
        # Add single entity with no connections
        e1 = Entity(id="e1", name="Lonely", entity_type="person", workspace_id=workspace_id)
        self.engine.add_entity(e1)
        
        count = self.engine.build_communities(workspace_id, min_community_size=2)
        
        assert count == 0


class TestGraphRAGEngineGlobalSearch:
    """Tests for map-reduce global search"""
    
    def setup_method(self):
        self.engine = GraphRAGEngine()
        self.engine._llm_client = None
    
    def test_global_search_returns_summaries(self):
        """Test global search returns community summaries"""
        workspace_id = "test_ws"
        
        # Add entities and build community
        e1 = Entity(id="e1", name="Marketing", entity_type="project", workspace_id=workspace_id)
        e2 = Entity(id="e2", name="Campaign", entity_type="task", workspace_id=workspace_id)
        self.engine.add_entity(e1)
        self.engine.add_entity(e2)
        
        r1 = Relationship(id="r1", from_entity="e1", to_entity="e2", rel_type="contains", workspace_id=workspace_id)
        self.engine.add_relationship(r1)
        
        self.engine.build_communities(workspace_id, min_community_size=2)
        
        # Search
        result = self.engine.global_search(workspace_id, "marketing strategy")
        
        assert result["mode"] == "global"
        assert "workspace_id" in result
    
    def test_global_search_empty_workspace(self):
        """Test global search on empty workspace"""
        result = self.engine.global_search("empty_ws", "anything")
        
        assert result["communities_found"] == 0
        assert "No communities found" in result["answer"]


class TestGraphRAGEngineLocalSearch:
    """Tests for local entity-centric search"""
    
    def setup_method(self):
        self.engine = GraphRAGEngine()
        self.engine._llm_client = None
    
    def test_local_search_finds_entity(self):
        """Test local search finds matching entity and neighbors"""
        workspace_id = "test_ws"
        
        e1 = Entity(id="e1", name="Sarah", entity_type="person", workspace_id=workspace_id)
        e2 = Entity(id="e2", name="Project Alpha", entity_type="project", workspace_id=workspace_id)
        self.engine.add_entity(e1)
        self.engine.add_entity(e2)
        
        r1 = Relationship(id="r1", from_entity="e1", to_entity="e2", rel_type="leads", workspace_id=workspace_id)
        self.engine.add_relationship(r1)
        
        result = self.engine.local_search(workspace_id, "Sarah")
        
        assert result["mode"] == "local"
        assert result["start_entity"] == "Sarah"
        assert result["entities_found"] >= 1
    
    def test_local_search_no_match(self):
        """Test local search returns error for no match"""
        result = self.engine.local_search("test_ws", "nonexistent")
        
        assert result["error"] == "No matching entity"
        assert result["entities_found"] == 0


class TestGraphRAGEngineBackwardCompatibility:
    """Tests to ensure backward compatibility with existing API"""
    
    def test_ingest_document_returns_expected_keys(self):
        """Test ingest_document returns expected response structure"""
        engine = GraphRAGEngine()
        engine._llm_client = None  # Use pattern fallback
        
        result = engine.ingest_document(
            workspace_id="ws1",
            doc_id="doc1",
            text="Meeting with project manager about the initiative.",
            source="email"
        )
        
        assert "entities" in result
        assert "relationships" in result
        assert "workspace_id" in result
    
    def test_query_auto_mode(self):
        """Test unified query with auto mode selection"""
        engine = GraphRAGEngine()
        
        # Global query
        result = engine.query("ws1", "What are the main themes?", mode="auto")
        assert result["mode"] == "global"
        
        # Local query
        result = engine.query("ws1", "Tell me about Sarah", mode="auto")
        assert result["mode"] == "local"
    
    def test_get_stats_structure(self):
        """Test get_stats returns expected structure"""
        engine = GraphRAGEngine()
        
        # Workspace-specific stats
        stats = engine.get_stats("ws1")
        assert "entities" in stats
        assert "relationships" in stats
        assert "communities" in stats
        assert "llm_enabled" in stats
        
        # Global stats
        stats = engine.get_stats()
        assert "total_entities" in stats
        assert "llm_enabled" in stats


class TestGraphRAGContextHelper:
    """Tests for helper function"""
    
    def test_get_graphrag_context_function(self):
        """Test the helper function works"""
        result = get_graphrag_context("ws1", "test query")
        assert isinstance(result, str)
