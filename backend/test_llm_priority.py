import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add backend to path
sys.path.append(os.getcwd())

from ai.nlp_engine import NaturalLanguageEngine

class TestLLMPriority(unittest.TestCase):
    
    @patch('ai.nlp_engine.OpenAI')
    @patch.dict(os.environ, {}, clear=True) # Start with empty env
    def test_priority_openai(self, mock_openai):
        """Test that OpenAI is picked first if available"""
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-openai", 
            "ANTHROPIC_API_KEY": "sk-anthropic"
        }):
            engine = NaturalLanguageEngine()
            # Should initialize with OpenAI key
            mock_openai.assert_called_with(api_key="sk-openai")
            print("✅ OpenAI Priority Verification Passed")

    @patch('ai.nlp_engine.OpenAI')
    @patch.dict(os.environ, {}, clear=True)
    def test_priority_anthropic(self, mock_openai):
        """Test that Anthropic is picked if OpenAI is missing"""
        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "sk-anthropic",
            "DEEPSEEK_API_KEY": "sk-deepseek"
        }):
            engine = NaturalLanguageEngine()
            # Should initialize with Anthropic key (passed to OpenAI client wrapper)
            mock_openai.assert_called_with(api_key="sk-anthropic")
            print("✅ Anthropic Priority Verification Passed")

    @patch('ai.nlp_engine.OpenAI')
    @patch.dict(os.environ, {}, clear=True)
    def test_priority_deepseek(self, mock_openai):
        """Test that DeepSeek is picked if others are missing"""
        with patch.dict(os.environ, {
            "DEEPSEEK_API_KEY": "sk-deepseek"
        }):
            engine = NaturalLanguageEngine()
            # Should initialize with DeepSeek key
            mock_openai.assert_called_with(api_key="sk-deepseek")
            print("✅ DeepSeek Priority Verification Passed")

if __name__ == '__main__':
    unittest.main()
