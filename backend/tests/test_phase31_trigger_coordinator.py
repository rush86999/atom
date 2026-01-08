import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ai_trigger_coordinator import (
    AITriggerCoordinator,
    DataCategory,
    TriggerDecision,
    on_data_ingested
)


class TestAITriggerCoordinator(unittest.TestCase):
    
    def setUp(self):
        self.coordinator = AITriggerCoordinator(workspace_id="test", user_id="test_user")
        self.coordinator._enabled = True  # Force enabled for tests
    
    def test_category_classification_finance(self):
        """Test that finance keywords are classified correctly"""
        text = "Please process this invoice for payment reconciliation"
        category, confidence = self.coordinator._classify_category(text)
        
        self.assertEqual(category, DataCategory.FINANCE)
        self.assertGreater(confidence, 0.3)
    
    def test_category_classification_sales(self):
        """Test that sales keywords are classified correctly"""
        text = "New lead in the pipeline from prospect company"
        category, confidence = self.coordinator._classify_category(text)
        
        self.assertEqual(category, DataCategory.SALES)
        self.assertGreater(confidence, 0.3)
    
    def test_category_classification_operations(self):
        """Test that operations keywords are classified correctly"""
        text = "Inventory check in warehouse shows low stock for shipping"
        category, confidence = self.coordinator._classify_category(text)
        
        self.assertEqual(category, DataCategory.OPERATIONS)
        self.assertGreater(confidence, 0.3)
    
    def test_category_classification_general(self):
        """Test that unknown text is classified as general"""
        text = "Hello world this is a random message"
        category, confidence = self.coordinator._classify_category(text)
        
        self.assertEqual(category, DataCategory.GENERAL)
        self.assertEqual(confidence, 0.0)
    
    def test_decision_high_confidence_triggers(self):
        """Test that high confidence triggers agent"""
        decision, agent, reasoning = self.coordinator._make_decision(
            category=DataCategory.FINANCE,
            confidence=0.8,
            source="document_upload",
            metadata=None
        )
        
        self.assertEqual(decision, TriggerDecision.TRIGGER_AGENT)
        self.assertEqual(agent, "finance_analyst")
    
    def test_decision_low_confidence_no_action(self):
        """Test that low confidence results in no action"""
        decision, agent, reasoning = self.coordinator._make_decision(
            category=DataCategory.FINANCE,
            confidence=0.2,
            source="document_upload",
            metadata=None
        )
        
        self.assertEqual(decision, TriggerDecision.NO_ACTION)
        self.assertIsNone(agent)
    
    def test_decision_no_agent_template(self):
        """Test that categories without agents result in no action"""
        decision, agent, reasoning = self.coordinator._make_decision(
            category=DataCategory.LEGAL,  # No agent configured
            confidence=0.9,
            source="document_upload",
            metadata=None
        )
        
        self.assertEqual(decision, TriggerDecision.NO_ACTION)
        self.assertIsNone(agent)
    
    async def test_evaluate_data_disabled_setting(self):
        """Test that disabled setting prevents triggering"""
        self.coordinator._enabled = False
        
        result = await self.coordinator.evaluate_data(
            data={"text": "Process this invoice for payment"},
            source="document_upload"
        )
        
        self.assertEqual(result["decision"], TriggerDecision.NO_ACTION.value)
        self.assertIn("disabled", result["reasoning"])
    
    async def test_evaluate_data_triggers_agent(self):
        """Test full evaluation flow triggers agent"""
        self.coordinator._enabled = True
        
        # Mock agent trigger
        with patch.object(self.coordinator, '_trigger_agent', new_callable=AsyncMock) as mock_trigger:
            result = await self.coordinator.evaluate_data(
                data={"text": "Invoice payment reconciliation expense budget"},
                source="document_upload"
            )
            
            # Should trigger finance analyst
            self.assertEqual(result["decision"], TriggerDecision.TRIGGER_AGENT.value)
            self.assertEqual(result["agent_template"], "finance_analyst")
            
            # Verify agent was triggered
            mock_trigger.assert_called_once()


class TestUserSettingsToggle(unittest.TestCase):
    """Test that user settings control the feature"""
    
    @patch("core.ai_trigger_coordinator.SessionLocal")
    async def test_setting_enabled(self, mock_session):
        """Test enabled setting allows coordinator"""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        
        with patch("core.ai_trigger_coordinator.UserPreferenceService") as mock_pref:
            mock_pref_instance = mock_pref.return_value
            mock_pref_instance.get_preference.return_value = True
            
            coordinator = AITriggerCoordinator("test", "user1")
            coordinator._enabled = None  # Reset cache
            
            enabled = await coordinator.is_enabled()
            self.assertTrue(enabled)
    
    @patch("core.ai_trigger_coordinator.SessionLocal")
    async def test_setting_disabled(self, mock_session):
        """Test disabled setting blocks coordinator"""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        
        with patch("core.ai_trigger_coordinator.UserPreferenceService") as mock_pref:
            mock_pref_instance = mock_pref.return_value
            mock_pref_instance.get_preference.return_value = False
            
            coordinator = AITriggerCoordinator("test", "user1")
            coordinator._enabled = None  # Reset cache
            
            enabled = await coordinator.is_enabled()
            self.assertFalse(enabled)


if __name__ == "__main__":
    unittest.main()
