import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.reasoning_chain import (
    ReasoningChain,
    ReasoningStep,
    ReasoningStepType,
    ReasoningTracker,
    get_reasoning_tracker,
)
from core.voice_service import VoiceService, VoiceTranscription


class TestReasoningChain(unittest.TestCase):
    
    def test_chain_creation(self):
        """Test creating a reasoning chain"""
        tracker = ReasoningTracker()
        chain_id = tracker.start_chain("test-exec-001")
        
        self.assertEqual(chain_id, "test-exec-001")
        self.assertIsNotNone(tracker.get_chain(chain_id))
    
    def test_add_steps(self):
        """Test adding steps to a chain"""
        tracker = ReasoningTracker()
        chain_id = tracker.start_chain()
        
        tracker.add_step(
            step_type=ReasoningStepType.INTENT_ANALYSIS,
            description="Analyzing user intent",
            inputs={"text": "test command"},
            outputs={"intent": "search"},
            confidence=0.9
        )
        
        tracker.add_step(
            step_type=ReasoningStepType.AGENT_SELECTION,
            description="Selected finance agent",
            inputs={"intent": "finance"},
            outputs={"agent": "finance_analyst"},
            confidence=0.85
        )
        
        chain = tracker.get_chain(chain_id)
        self.assertEqual(len(chain.steps), 2)
        self.assertEqual(chain.steps[0].step_type, ReasoningStepType.INTENT_ANALYSIS)
        self.assertEqual(chain.steps[1].step_type, ReasoningStepType.AGENT_SELECTION)
    
    def test_complete_chain(self):
        """Test completing a chain"""
        tracker = ReasoningTracker()
        chain_id = tracker.start_chain()
        
        tracker.add_step(
            step_type=ReasoningStepType.ACTION,
            description="Taking action",
            confidence=1.0
        )
        
        completed = tracker.complete_chain(outcome="Success", chain_id=chain_id)
        
        self.assertIsNotNone(completed.completed_at)
        self.assertEqual(completed.final_outcome, "Success")
        self.assertGreater(completed.total_duration_ms, 0)
    
    def test_mermaid_generation(self):
        """Test Mermaid diagram generation"""
        tracker = ReasoningTracker()
        chain_id = tracker.start_chain()
        
        tracker.add_step(ReasoningStepType.INTENT_ANALYSIS, "Step 1")
        tracker.add_step(ReasoningStepType.DECISION, "Step 2")
        tracker.add_step(ReasoningStepType.CONCLUSION, "Step 3")
        
        chain = tracker.get_chain(chain_id)
        mermaid = chain.to_mermaid()
        
        self.assertIn("graph TD", mermaid)
        self.assertIn("step0", mermaid)
        self.assertIn("step1", mermaid)
        self.assertIn("step2", mermaid)
        self.assertIn("-->", mermaid)


class TestVoiceService(unittest.TestCase):
    
    def setUp(self):
        self.service = VoiceService()
    
    async def test_transcribe_fallback(self):
        """Test fallback transcription when no API key"""
        with patch.object(self.service, '_whisper_available', False):
            result = await self.service.transcribe_audio(
                audio_bytes=b"fake audio data",
                audio_format="webm"
            )
            
            self.assertIsInstance(result, VoiceTranscription)
            self.assertEqual(result.confidence, 0.0)  # Fallback has zero confidence
    
    @patch("core.voice_service.get_atom_agent")
    async def test_process_voice_command(self, mock_atom):
        """Test processing a voice command through Atom"""
        mock_atom_instance = MagicMock()
        mock_atom.return_value = mock_atom_instance
        mock_atom_instance.execute = AsyncMock(return_value={
            "final_output": "Command processed",
            "actions_executed": []
        })
        
        result = await self.service.process_voice_command(
            transcribed_text="Analyze my expenses",
            user_id="test_user"
        )
        
        self.assertTrue(result.get("success"))
        self.assertIn("reasoning_chain_id", result)


class TestGlobalTracker(unittest.TestCase):
    
    def test_singleton_tracker(self):
        """Test global tracker singleton"""
        tracker1 = get_reasoning_tracker()
        tracker2 = get_reasoning_tracker()
        
        self.assertIs(tracker1, tracker2)


if __name__ == "__main__":
    unittest.main()
