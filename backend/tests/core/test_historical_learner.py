"""
Tests for HistoricalLifecycleLearner - historical learning from past executions.

Target: 75%+ line coverage, 60%+ branch coverage
File: backend/core/historical_learner.py (52 lines)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import sys

# Mock the problematic imports before importing historical_learner
# This avoids the SQLAlchemy duplicate table issue (SaaSTier defined in both core/models.py and saas/models.py)
sys.modules['core.business_intelligence'] = MagicMock()
sys.modules['core.knowledge_extractor'] = MagicMock()

from core.historical_learner import HistoricalLifecycleLearner


class TestHistoricalLifecycleLearner:
    """Test suite for HistoricalLifecycleLearner"""

    @pytest.fixture
    def mock_lancedb(self):
        """Mock LanceDB handler"""
        lancedb = MagicMock()
        lancedb.search = MagicMock(return_value=[])
        return lancedb

    @pytest.fixture
    def mock_extractor(self):
        """Mock KnowledgeExtractor"""
        extractor = AsyncMock()
        extractor.extract_knowledge = AsyncMock(return_value={
            "entities": [],
            "relationships": []
        })
        return extractor

    @pytest.fixture
    def mock_biz_intel(self):
        """Mock BusinessEventIntelligence"""
        biz_intel = AsyncMock()
        biz_intel.process_extracted_events = AsyncMock()
        return biz_intel

    @pytest.fixture
    def learner(self, mock_lancedb, mock_extractor, mock_biz_intel):
        """Create HistoricalLifecycleLearner instance with mocked dependencies"""
        with patch('core.historical_learner.get_lancedb_handler', return_value=mock_lancedb), \
             patch('core.historical_learner.KnowledgeExtractor', return_value=mock_extractor), \
             patch('core.historical_learner.BusinessEventIntelligence', return_value=mock_biz_intel):
            learner = HistoricalLifecycleLearner()
            learner.lancedb = mock_lancedb
            learner.extractor = mock_extractor
            learner.biz_intel = mock_biz_intel
            return learner

    # Test 1: Initialization
    def test_initialization(self):
        """Test learner initializes with correct dependencies"""
        with patch('core.historical_learner.get_lancedb_handler') as mock_get_lancedb, \
             patch('core.historical_learner.KnowledgeExtractor') as mock_extractor_cls, \
             patch('core.historical_learner.BusinessEventIntelligence') as mock_biz_intel_cls:

            mock_lancedb = MagicMock()
            mock_get_lancedb.return_value = mock_lancedb

            learner = HistoricalLifecycleLearner(ai_service="test_ai", db_session="test_db")

            assert learner.lancedb == mock_lancedb
            mock_extractor_cls.assert_called_once_with("test_ai")
            mock_biz_intel_cls.assert_called_once_with("test_db")

    # Test 2: Learn from history with no documents
    @pytest.mark.asyncio
    async def test_learn_from_history_no_documents(self, learner, mock_lancedb):
        """Test learning when no historical documents exist"""
        mock_lancedb.search.return_value = []

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        # Should search for documents
        mock_lancedb.search.assert_called_once_with(
            table_name="atom_communications",
            query="business correspondence",
            user_id="user-123",
            limit=100
        )
        # Should not call extractor or biz_intel
        learner.extractor.extract_knowledge.assert_not_called()
        learner.biz_intel.process_extracted_events.assert_not_called()

    # Test 3: Learn from history with documents but no knowledge
    @pytest.mark.asyncio
    async def test_learn_from_history_no_knowledge_extracted(self, learner, mock_lancedb, mock_extractor):
        """Test learning when documents exist but no knowledge extracted"""
        mock_lancedb.search.return_value = [
            {"text": "Meeting notes from yesterday"},
            {"text": "Email discussion about project"}
        ]
        mock_extractor.extract_knowledge.return_value = {
            "entities": [],
            "relationships": []
        }

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        # Should process each document
        assert mock_extractor.extract_knowledge.call_count == 2
        # Should not call biz_intel (no entities or relationships)
        learner.biz_intel.process_extracted_events.assert_not_called()

    # Test 4: Learn from history with entities extracted
    @pytest.mark.asyncio
    async def test_learn_from_history_with_entities(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test learning when entities are extracted"""
        mock_lancedb.search.return_value = [
            {"text": "John Doe from Acme Corp discussed the Q1 project"}
        ]
        mock_extractor.extract_knowledge.return_value = {
            "entities": [
                {"name": "John Doe", "type": "Person", "organization": "Acme Corp"}
            ],
            "relationships": []
        }

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        # Should call biz_intel with extracted knowledge
        mock_biz_intel.process_extracted_events.assert_called_once()
        call_args = mock_biz_intel.process_extracted_events.call_args
        assert call_args[0][0]["entities"][0]["name"] == "John Doe"
        assert call_args[0][1] == "ws-123"

    # Test 5: Learn from history with relationships extracted
    @pytest.mark.asyncio
    async def test_learn_from_history_with_relationships(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test learning when relationships are extracted"""
        mock_lancedb.search.return_value = [
            {"text": "Project Alpha depends on Project Beta"}
        ]
        mock_extractor.extract_knowledge.return_value = {
            "entities": [],
            "relationships": [
                {"from": "Project Alpha", "to": "Project Beta", "type": "depends_on"}
            ]
        }

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        # Should call biz_intel with extracted knowledge
        mock_biz_intel.process_extracted_events.assert_called_once()

    # Test 6: Learn from history with both entities and relationships
    @pytest.mark.asyncio
    async def test_learn_from_history_with_entities_and_relationships(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test learning when both entities and relationships are extracted"""
        mock_lancedb.search.return_value = [
            {"text": "John from Acme is leading Project Alpha"}
        ]
        mock_extractor.extract_knowledge.return_value = {
            "entities": [{"name": "John", "type": "Person"}],
            "relationships": [{"from": "John", "to": "Project Alpha", "type": "leads"}]
        }

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        mock_biz_intel.process_extracted_events.assert_called_once()

    # Test 7: Learn from history with multiple documents
    @pytest.mark.asyncio
    async def test_learn_from_history_multiple_documents(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test learning from multiple historical documents"""
        docs = [
            {"text": f"Document {i} content"} for i in range(5)
        ]
        mock_lancedb.search.return_value = docs
        mock_extractor.extract_knowledge.return_value = {
            "entities": [{"name": "Test Entity"}],
            "relationships": []
        }

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        # Should process all documents
        assert mock_extractor.extract_knowledge.call_count == 5
        assert mock_biz_intel.process_extracted_events.call_count == 5

    # Test 8: Learn from history handles empty text field
    @pytest.mark.asyncio
    async def test_learn_from_history_handles_missing_text_field(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test learning when document has no text field"""
        mock_lancedb.search.return_value = [
            {"other_field": "some data"},
            {"text": "Valid document"}
        ]

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        # Should still call extractor for both (empty string for missing text)
        assert mock_extractor.extract_knowledge.call_count == 2

    # Test 9: LanceDB search error handling
    @pytest.mark.asyncio
    async def test_learn_from_history_lancedb_error(self, learner, mock_lancedb):
        """Test learning when LanceDB search fails"""
        mock_lancedb.search.side_effect = Exception("LanceDB connection failed")

        # Should raise exception
        with pytest.raises(Exception, match="LanceDB connection failed"):
            await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

    # Test 10: Extractor error handling
    @pytest.mark.asyncio
    async def test_learn_from_history_extractor_error(self, learner, mock_lancedb, mock_extractor):
        """Test learning when knowledge extraction fails"""
        mock_lancedb.search.return_value = [{"text": "Test document"}]
        mock_extractor.extract_knowledge.side_effect = Exception("Extraction failed")

        # Should raise exception
        with pytest.raises(Exception, match="Extraction failed"):
            await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

    # Test 11: Business intelligence error handling
    @pytest.mark.asyncio
    async def test_learn_from_history_biz_intel_error(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test learning when business intelligence processing fails"""
        mock_lancedb.search.return_value = [{"text": "Test document"}]
        mock_extractor.extract_knowledge.return_value = {
            "entities": [{"name": "Test"}],
            "relationships": []
        }
        mock_biz_intel.process_extracted_events.side_effect = Exception("BI processing failed")

        # Should raise exception
        with pytest.raises(Exception, match="BI processing failed"):
            await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

    # Test 12: Verify correct parameters passed to LanceDB search
    @pytest.mark.asyncio
    async def test_learn_from_history_lancedb_search_params(self, learner, mock_lancedb):
        """Test that correct parameters are passed to LanceDB search"""
        mock_lancedb.search.return_value = []

        await learner.learn_from_history(
            workspace_id="test-workspace",
            user_id="test-user-456"
        )

        mock_lancedb.search.assert_called_once_with(
            table_name="atom_communications",
            query="business correspondence",
            user_id="test-user-456",
            limit=100
        )

    # Test 13: Verify correct parameters passed to extractor
    @pytest.mark.asyncio
    async def test_learn_from_history_extractor_params(self, learner, mock_lancedb, mock_extractor):
        """Test that correct parameters are passed to knowledge extractor"""
        mock_lancedb.search.return_value = [
            {"text": "Test content"}
        ]

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        call_args = mock_extractor.extract_knowledge.call_args
        # Check both positional and keyword arguments
        assert "Test content" in call_args[0] or call_args[1].get("text") == "Test content"
        assert "historical_comm" in call_args[0] or call_args[1].get("source") == "historical_comm"

    # Test 14: Verify correct parameters passed to business intelligence
    @pytest.mark.asyncio
    async def test_learn_from_history_biz_intel_params(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test that correct parameters are passed to business intelligence"""
        mock_lancedb.search.return_value = [{"text": "Test"}]
        mock_extractor.extract_knowledge.return_value = {
            "entities": [{"name": "Test"}],
            "relationships": []
        }

        await learner.learn_from_history(workspace_id="ws-abc", user_id="user-xyz")

        call_args = mock_biz_intel.process_extracted_events.call_args
        assert call_args[0][0]["entities"][0]["name"] == "Test"
        assert call_args[0][1] == "ws-abc"

    # Test 15: Large document set (pagination test)
    @pytest.mark.asyncio
    async def test_learn_from_history_large_document_set(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test learning handles large document sets (limit 100)"""
        # Simulate 100 documents (current limit)
        docs = [{"text": f"Document {i}"} for i in range(100)]
        mock_lancedb.search.return_value = docs
        mock_extractor.extract_knowledge.return_value = {
            "entities": [],
            "relationships": []
        }

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        # Should process all 100 documents
        assert mock_extractor.extract_knowledge.call_count == 100
        # Should not call biz_intel (no knowledge extracted)
        mock_biz_intel.process_extracted_events.assert_not_called()

    # Test 16: Knowledge extraction with complex entities
    @pytest.mark.asyncio
    async def test_learn_from_history_complex_entities(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test learning with complex entity structures"""
        mock_lancedb.search.return_value = [{"text": "Complex business data"}]
        mock_extractor.extract_knowledge.return_value = {
            "entities": [
                {"name": "Person1", "type": "Person", "role": "CEO"},
                {"name": "Org1", "type": "Organization"},
                {"name": "Project1", "type": "Project", "status": "active"}
            ],
            "relationships": [
                {"from": "Person1", "to": "Org1", "type": "works_for"},
                {"from": "Person1", "to": "Project1", "type": "manages"}
            ]
        }

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        mock_biz_intel.process_extracted_events.assert_called_once()
        call_args = mock_biz_intel.process_extracted_events.call_args
        knowledge = call_args[0][0]
        assert len(knowledge["entities"]) == 3
        assert len(knowledge["relationships"]) == 2

    # Test 17: Sequential processing of documents
    @pytest.mark.asyncio
    async def test_learn_from_history_sequential_processing(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test that documents are processed sequentially"""
        docs = [
            {"text": "First document"},
            {"text": "Second document"},
            {"text": "Third document"}
        ]
        mock_lancedb.search.return_value = docs

        # Track call order
        call_order = []
        async def side_effect(text, source):
            call_order.append(text)
            return {"entities": [{"name": f"Entity from {text}"}], "relationships": []}

        mock_extractor.extract_knowledge.side_effect = side_effect

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        # Verify sequential processing
        assert call_order == ["First document", "Second document", "Third document"]
        assert mock_biz_intel.process_extracted_events.call_count == 3

    # Test 18: Mixed knowledge extraction (some docs have knowledge, some don't)
    @pytest.mark.asyncio
    async def test_learn_from_history_mixed_knowledge_extraction(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test learning when some documents have knowledge and some don't"""
        docs = [
            {"text": "Doc with knowledge"},
            {"text": "Doc without knowledge"},
            {"text": "Another doc with knowledge"}
        ]
        mock_lancedb.search.return_value = docs

        # Alternate between having and not having knowledge
        call_count = [0]
        async def side_effect(text, source):
            call_count[0] += 1
            if call_count[0] % 2 == 1:
                return {"entities": [{"name": f"Entity {call_count[0]}"}], "relationships": []}
            else:
                return {"entities": [], "relationships": []}

        mock_extractor.extract_knowledge.side_effect = side_effect

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        # biz_intel should only be called for docs with knowledge
        assert mock_biz_intel.process_extracted_events.call_count == 2

    # Test 19: Workspace ID propagation
    @pytest.mark.asyncio
    async def test_learn_from_history_workspace_id_propagation(self, learner, mock_lancedb, mock_extractor, mock_biz_intel):
        """Test that workspace ID is correctly propagated to business intelligence"""
        mock_lancedb.search.return_value = [{"text": "Test"}]
        mock_extractor.extract_knowledge.return_value = {
            "entities": [{"name": "Test"}],
            "relationships": []
        }

        workspace_id = "special-workspace-789"
        await learner.learn_from_history(workspace_id=workspace_id, user_id="user-123")

        # Verify workspace_id is passed correctly
        call_args = mock_biz_intel.process_extracted_events.call_args
        assert call_args[0][1] == workspace_id

    # Test 20: User ID in LanceDB query
    @pytest.mark.asyncio
    async def test_learn_from_history_user_id_in_query(self, learner, mock_lancedb):
        """Test that user ID is correctly used in LanceDB query"""
        mock_lancedb.search.return_value = []

        user_id = "special-user-999"
        await learner.learn_from_history(workspace_id="ws-123", user_id=user_id)

        # Verify user_id is passed to LanceDB
        call_args = mock_lancedb.search.call_args
        assert call_args[1]["user_id"] == user_id


class TestHistoricalLifecycleLearnerEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.fixture
    def learner(self):
        """Create learner with all dependencies mocked"""
        with patch('core.historical_learner.get_lancedb_handler') as mock_get_lancedb, \
             patch('core.historical_learner.KnowledgeExtractor') as mock_extractor_cls, \
             patch('core.historical_learner.BusinessEventIntelligence') as mock_biz_intel_cls:

            mock_lancedb = MagicMock()
            mock_extractor = AsyncMock()
            mock_biz_intel = AsyncMock()

            mock_get_lancedb.return_value = mock_lancedb
            mock_extractor_cls.return_value = mock_extractor
            mock_biz_intel_cls.return_value = mock_biz_intel

            learner = HistoricalLifecycleLearner()
            learner.lancedb = mock_lancedb
            learner.extractor = mock_extractor
            learner.biz_intel = mock_biz_intel

            return learner

    # Test 21: Empty string in text field
    @pytest.mark.asyncio
    async def test_empty_string_text_field(self, learner):
        """Test handling of empty string in text field"""
        learner.lancedb.search.return_value = [{"text": ""}]
        learner.extractor.extract_knowledge.return_value = {
            "entities": [],
            "relationships": []
        }

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        # Should still process empty string
        learner.extractor.extract_knowledge.assert_called_once()
        # Verify the call was made with empty content
        call_args = learner.extractor.extract_knowledge.call_args
        assert "" in call_args[0] or call_args[1].get("text") == ""

    # Test 22: Unicode content in documents
    @pytest.mark.asyncio
    async def test_unicode_content(self, learner):
        """Test handling of unicode content in documents"""
        learner.lancedb.search.return_value = [
            {"text": "Document with emoji 🎉 and unicode 中文"}
        ]
        learner.extractor.extract_knowledge.return_value = {
            "entities": [],
            "relationships": []
        }

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        call_args = learner.extractor.extract_knowledge.call_args
        assert "emoji 🎉" in call_args[0][0]

    # Test 23: Very long document content
    @pytest.mark.asyncio
    async def test_very_long_document(self, learner):
        """Test handling of very long document content"""
        long_text = "Word " * 10000  # 50,000 characters
        learner.lancedb.search.return_value = [{"text": long_text}]
        learner.extractor.extract_knowledge.return_value = {
            "entities": [],
            "relationships": []
        }

        await learner.learn_from_history(workspace_id="ws-123", user_id="user-123")

        call_args = learner.extractor.extract_knowledge.call_args
        assert len(call_args[0][0]) == len(long_text)
