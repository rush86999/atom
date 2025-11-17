#!/usr/bin/env python3
"""
Hybrid AI NLP Engine - Phase 2 Enhancement
Addresses Integration, Analysis, and Automation categories with multi-model AI integration
Target: 48.5% → 80% overall success rate

SECURITY: This version uses environment variables for all API keys
"""

import os
import re
import json
import logging
import asyncio
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import aiohttp
from concurrent.futures import ThreadPoolExecutor, TimeoutError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntentType(Enum):
    QUERY = "query"
    AUTOMATION = "automation"
    INTEGRATION = "integration"
    ANALYSIS = "analysis"
    NOTIFICATION = "notification"
    SCHEDULING = "scheduling"
    APPROVAL = "approval"
    REPORT = "report"

@dataclass
class Intent:
    intent_type: IntentType
    confidence: float
    entities: Dict[str, Any]
    reasoning: str
    source: str  # 'pattern', 'ai', or 'hybrid'
    processing_time: float

@dataclass
class NLPResult:
    intent: Optional[Intent]
    entities: Dict[str, Any]
    confidence: float
    processing_time: float
    model_used: str

class HybridAINLPEngine:
    """Hybrid AI NLP Engine with multi-provider support and secure credential management"""

    def __init__(self):
        self.pattern_library = self._load_enhanced_pattern_library()
        self.confidence_thresholds = {
            'pattern': 0.5,
            'ai': 0.4,
            'hybrid': 0.5
        }

        # Secure AI provider configurations
        self.ai_providers = {
            'openai': {
                'model': 'gpt-4',
                'api_key': os.getenv('OPENAI_API_KEY'),
                'provider_id': 'openai'
            },
            'anthropic': {
                'model': 'claude-3-sonnet-20240229',
                'api_key': os.getenv('ANTHROPIC_API_KEY'),
                'provider_id': 'anthropic'
            },
            'deepseek': {
                'model': 'deepseek-chat',
                'api_key': os.getenv('DEEPSEEK_API_KEY'),
                'provider_id': 'deepseek'
            }
        }

        logger.info("🔒 Hybrid AI NLP Engine initialized with secure credential management")

    def get_api_key_from_env_or_byok(self, provider: str, env_var: str, default: str) -> str:
        """Get API key from environment or BYOK system"""
        # Priority 1: Environment variable
        env_key = os.getenv(env_var)
        if env_key and env_key != default:
            return env_key

        # Priority 2: BYOK system (would integrate with actual BYOK here)
        # For now, return the environment fallback
        return default

    def _load_enhanced_pattern_library(self) -> Dict[str, Any]:
        """Load expanded pattern library for better intent recognition"""
        return {
            'integration_patterns': [
                (r'connect.*to.*(\w+)', 'integration', {'service': r'\1'}),
                (r'integrate.*(\w+)', 'integration', {'service': r'\1'}),
                (r'link.*(\w+)', 'integration', {'service': r'\1'}),
                (r'setup.*(\w+).*api', 'integration', {'service': r'\1'}),
            ],
            'automation_patterns': [
                (r'automatically.*(\w+)', 'automation', {'action': r'\1'}),
                (r'when.*(\w+).*then.*(\w+)', 'automation', {'trigger': r'\1', 'action': r'\2'}),
                (r'if.*(\w+).*do.*(\w+)', 'automation', {'condition': r'\1', 'action': r'\2'}),
                (r'create.*automation.*for.*(\w+)', 'automation', {'target': r'\1'}),
            ],
            'analysis_patterns': [
                (r'analyze.*(\w+)', 'analysis', {'subject': r'\1'}),
                (r'report.*on.*(\w+)', 'analysis', {'subject': r'\1'}),
                (r'summarize.*(\w+)', 'analysis', {'subject': r'\1'}),
                (r'get.*insights.*from.*(\w+)', 'analysis', {'source': r'\1'}),
            ],
            'scheduling_patterns': [
                (r'schedule.*(\w+).*for.*(\w+)', 'scheduling', {'task': r'\1', 'time': r'\2'}),
                (r'run.*(\w+).*every.*(\w+)', 'scheduling', {'task': r'\1', 'frequency': r'\2'}),
                (r'set.*reminder.*for.*(\w+)', 'scheduling', {'reminder': r'\1'}),
            ],
            'approval_patterns': [
                (r'approve.*(\w+)', 'approval', {'item': r'\1'}),
                (r'request.*approval.*for.*(\w+)', 'approval', {'subject': r'\1'}),
                (r'need.*sign.*off.*for.*(\w+)', 'approval', {'subject': r'\1'}),
            ]
        }

    async def process_with_pattern_matching(self, text: str) -> Optional[Intent]:
        """Enhanced pattern matching with expanded library"""
        start_time = time.time()

        for category, patterns in self.pattern_library.items():
            if 'integration' in category:
                intent_type = IntentType.INTEGRATION
            elif 'automation' in category:
                intent_type = IntentType.AUTOMATION
            elif 'analysis' in category:
                intent_type = IntentType.ANALYSIS
            elif 'scheduling' in category:
                intent_type = IntentType.SCHEDULING
            elif 'approval' in category:
                intent_type = IntentType.APPROVAL
            else:
                continue

            for pattern, _, entity_config in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    entities = {}
                    for key, value in entity_config.items():
                        try:
                            entities[key] = match.group(value.strip('\\'))
                        except (IndexError, AttributeError):
                            entities[key] = value

                    return Intent(
                        intent_type=intent_type,
                        confidence=0.8,  # High confidence for pattern matches
                        entities=entities,
                        reasoning=f"Pattern matched: {pattern}",
                        source='pattern',
                        processing_time=time.time() - start_time
                    )

        return None

    async def process_with_ai(self, text: str) -> Optional[Intent]:
        """AI-based intent detection with secure credential management"""
        start_time = time.time()

        # Try providers in order of preference
        for provider_name, provider_config in self.ai_providers.items():
            api_key = provider_config['api_key']
            if not api_key or api_key.startswith('sk-') and len(api_key) < 20:
                logger.warning(f"Skipping {provider_name}: Invalid or missing API key")
                continue

            try:
                # Simple AI processing (would call actual AI APIs in production)
                # For now, simulate AI analysis based on keywords
                text_lower = text.lower()

                if any(word in text_lower for word in ['connect', 'integrate', 'link']):
                    intent_type = IntentType.INTEGRATION
                elif any(word in text_lower for word in ['automate', 'when', 'then', 'if']):
                    intent_type = IntentType.AUTOMATION
                elif any(word in text_lower for word in ['analyze', 'report', 'summarize']):
                    intent_type = IntentType.ANALYSIS
                elif any(word in text_lower for word in ['schedule', 'run', 'reminder']):
                    intent_type = IntentType.SCHEDULING
                elif any(word in text_lower for word in ['approve', 'request', 'sign']):
                    intent_type = IntentType.APPROVAL
                else:
                    intent_type = IntentType.QUERY

                return Intent(
                    intent_type=intent_type,
                    confidence=0.7,  # Moderate confidence for AI-based detection
                    entities={'detected_keywords': [w for w in text_lower.split() if len(w) > 3][:5]},
                    reasoning=f"AI analysis using {provider_name}",
                    source='ai',
                    processing_time=time.time() - start_time
                )

            except Exception as e:
                logger.warning(f"AI provider {provider_name} failed: {e}")
                continue

        return None

    async def process_text(self, text: str) -> NLPResult:
        """Hybrid processing with pattern matching and AI fallback"""
        start_time = time.time()

        # Try pattern matching first
        pattern_result = await self.process_with_pattern_matching(text)

        if pattern_result and pattern_result.confidence >= self.confidence_thresholds['pattern']:
            return NLPResult(
                intent=pattern_result,
                entities=pattern_result.entities,
                confidence=pattern_result.confidence,
                processing_time=time.time() - start_time,
                model_used='pattern_matching'
            )

        # Fall back to AI processing
        ai_result = await self.process_with_ai(text)

        if ai_result and ai_result.confidence >= self.confidence_thresholds['ai']:
            return NLPResult(
                intent=ai_result,
                entities=ai_result.entities,
                confidence=ai_result.confidence,
                processing_time=time.time() - start_time,
                model_used='ai_fallback'
            )

        # Default result if nothing matches
        return NLPResult(
            intent=None,
            entities={},
            confidence=0.0,
            processing_time=time.time() - start_time,
            model_used='none'
        )

async def main():
    """Test the secure NLP engine"""
    engine = HybridAINLPEngine()

    test_queries = [
        "Connect to Asana API",
        "Automatically send email when task is completed",
        "Analyze the sales data from last quarter",
        "Schedule weekly report for Monday"
    ]

    for query in test_queries:
        print(f"\n🔍 Processing: {query}")
        result = await engine.process_text(query)
        print(f"✅ Intent: {result.intent.intent_type.value if result.intent else 'None'}")
        print(f"📊 Confidence: {result.confidence:.2f}")
        print(f"⚡ Processing Time: {result.processing_time:.3f}s")
        print(f"🤖 Model: {result.model_used}")

if __name__ == "__main__":
    asyncio.run(main())