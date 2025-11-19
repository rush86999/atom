#!/usr/bin/env python3
"""
Enhanced AI Validator for Complex Workflow Testing
Uses multi-provider AI analysis to find subtle bugs in workflow execution
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from independent_ai_validator.core.validator_engine import IndependentAIValidator, MarketingClaim, ValidationRequest
from independent_ai_validator.core.credential_manager import CredentialManager
import json
from datetime import datetime
from typing import Dict, List, Any

class EnhancedWorkflowValidator:
    """Use AI validator to analyze workflow behavior and find bugs"""
    
    def __init__(self):
        self.credential_manager = CredentialManager()
        self.validator = None
        self.bugs_found = []
        
    async def initialize(self):
        """Initialize AI validator with credentials"""
        print("🔐 Initializing AI Validator...")
        
        # Load credentials
        credentials_loaded = self.credential_manager.load_credentials()
        
        if credentials_loaded:
            print("✅ Credentials loaded")
            
            # Initialize validator
            self.validator = IndependentAIValidator(self.credential_manager)
            await self.validator.initialize()
            print("✅ AI Validator initialized")
            return True
        else:
            print("⚠️  No credentials loaded - AI validation limited")
            return False
    
    async def validate_workflow_correctness(self, workflow_name: str, input_data: Dict, output_data: Dict, expected_behavior: str) -> Dict[str, Any]:
        """
        Use AI to validate if workflow output matches expected behavior
        Cross-validates across multiple AI providers
        """
        print(f"\n🤖 AI-Validating: {workflow_name}")
        
        if not self.validator:
            return {"validated": False, "reason": "No AI validator available"}
        
        # Create and register dynamic claim
        claim_id = f"workflow_{workflow_name}"
        claim = MarketingClaim(
            id=claim_id,
            claim=f"The workflow '{workflow_name}' correctly processes the input and produces appropriate output according to this specification: {expected_behavior}",
            claim_type="workflow_validation",
            category="workflow_quality",
            description=f"Validation of {workflow_name} execution",
            validation_criteria=["Correctness", "Completeness", "Format Compliance"]
        )
        
        # Register claim in validator's database
        self.validator.claims_database[claim_id] = claim
        
        # Run validation
        result = await self.validator.validate_claim(
            claim_id=claim_id,
            evidence={
                "workflow_name": workflow_name,
                "input": input_data,
                "output": output_data,
                "expected_behavior": expected_behavior
            }
        )
        
        # Analyze results
        consensus_score = result.consensus_score
        provider_verdicts = {
            prov: res.get('assessment', 'UNKNOWN') for prov, res in result.provider_analyses.items()
        }
        
        print(f"  Consensus Score: {consensus_score:.1%}")
        print(f"  Provider Verdicts: {provider_verdicts}")
        
        # If consensus is low, it's likely a bug
        if consensus_score < 0.5:
            bug_description = f"Workflow '{workflow_name}' output quality issue detected by AI analysis"
            reasoning = []
            for provider, prov_result in result.provider_analyses.items():
                reasoning_text = prov_result.get('reasoning', 'No reasoning provided') if isinstance(prov_result, dict) else getattr(prov_result, 'reasoning', 'No reasoning provided')
                reasoning.append(f"{provider}: {reasoning_text[:150]}...")
            
            self.bugs_found.append({
                "type": "ai_detected_issue",
                "workflow": workflow_name,
                "severity": "high" if consensus_score < 0.3 else "medium",
                "consensus_score": consensus_score,
                "description": bug_description,
                "ai_reasoning": reasoning,
                "provider_verdicts": provider_verdicts
            })
            
            print(f"  🐛 Bug detected! Low consensus: {consensus_score:.1%}")
            return {"validated": False, "bug_detected": True, "consensus": consensus_score}
        
        print(f"  ✅ Passed AI validation")
        return {"validated": True, "consensus": consensus_score}
    
    async def test_customer_support_workflow_quality(self):
        """Test customer support workflow with AI quality analysis"""
        print("\n" + "="*70)
        print("🔍 AI-Enhanced Test: Customer Support Workflow Quality")
        print("="*70)
        
        # Test case 1: Order inquiry
        input1 = {
            "customer_message": "My order #12345 hasn't arrived yet and I need it urgently",
            "customer_id": "cust_789",
            "order_id": "12345"
        }
        
        # Simulate workflow output (in real test, would call actual workflow)
        simulated_output1 = {
            "intent": "order_status_inquiry",
            "urgency": "high",
            "entities": {"order_id": "12345"},
            "suggested_response": "I apologize for the delay. Let me check your order #12345 status immediately."
        }
        
        expected_behavior1 = "Should detect order inquiry intent, recognize urgency, extract order number, and suggest empathetic response"
        
        result1 = await self.validate_workflow_correctness(
            "customer_support_order_inquiry",
            input1,
            simulated_output1,
            expected_behavior1
        )
        
        # Test case 2: Complex multi-issue query
        input2 = {
            "customer_message": "I want to return my broken laptop and get a refund, but also I can't log into my account",
            "customer_id": "cust_456"
        }
        
        simulated_output2 = {
            "intent": "return_request",  # Only captured first intent!
            "entities": {"product": "laptop", "condition": "broken"}
        }
        
        expected_behavior2 = "Should detect BOTH return request AND account access issue, prioritize properly, extract all entities"
        
        result2 = await self.validate_workflow_correctness(
            "customer_support_multi_issue",
            input2,
            simulated_output2,
            expected_behavior2
        )
        
        # This should find a bug - workflow only detected one intent
        if not result2.get("validated"):
            print("\n🐛 AI FOUND BUG: Workflow fails to detect multiple intents in single message")
    
    async def test_content_generation_quality(self):
        """Test AI content generation workflow quality"""
        print("\n" + "="*70)
        print("🔍 AI-Enhanced Test: Content Generation Quality")
        print("="*70)
        
        input_brief = {
            "topic": "Benefits of workflow automation",
            "tone": "professional",
            "length": "150-200 words",
            "key_points": ["time savings", "error reduction", "scalability"]
        }
        
        # Simulated AI-generated content (would come from real workflow)
        simulated_content = {
            "title": "Workflow Automation Benefits",
            "content": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.",
            "word_count": 85  # Too short!
        }
        
        expected_behavior = "Generate professional content about automation benefits, include all key points, meet word count requirement (150-200 words)"
        
        result = await self.validate_workflow_correctness(
            "content_generation",
            input_brief,
            simulated_content,
            expected_behavior
        )
        
        # Should detect: too short, missing key points, lorem ipsum placeholder
        if not result.get("validated"):
            print("\n🐛 AI FOUND BUG: Content generation produces low-quality output")
    
    async def run_enhanced_validation(self):
        """Run all enhanced AI validation tests"""
        print("🚀 Enhanced AI Workflow Validation")
        print("Using GLM, Anthropic, DeepSeek for cross-validation")
        print("="*70)
        
        # Initialize
        initialized = await self.initialize()
        
        if not initialized:
            print("\n⚠️  Cannot run AI validation without credentials")
            print("Set environment variables: OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.")
            return
        
        # Run tests
        await self.test_customer_support_workflow_quality()
        await self.test_content_generation_quality()
        
        # Summary
        print("\n" + "="*70)
        print("📊 AI-ENHANCED VALIDATION RESULTS")
        print("="*70)
        print(f"AI-Detected Bugs: {len(self.bugs_found)}")
        
        for i, bug in enumerate(self.bugs_found, 1):
            print(f"\n🐛 Bug #{i}: {bug['description']}")
            print(f"   Severity: {bug['severity'].upper()}")
            print(f"   Consensus: {bug['consensus_score']:.1%}")
            print(f"   AI Reasoning:")
            for reasoning in bug['ai_reasoning'][:2]:  # Show first 2
                print(f"     - {reasoning}")
        
        # Save report
        report = {
            "timestamp": datetime.now().isoformat(),
            "validation_method": "multi_provider_ai_consensus",
            "providers_used": ["glm", "anthropic", "deepseek"],
            "bugs_found": len(self.bugs_found),
            "bugs": self.bugs_found
        }
        
        report_file = f"ai_validation_bugs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📁 AI validation report: {report_file}")

async def main():
    """Run enhanced AI validation"""
    validator = EnhancedWorkflowValidator()
    await validator.run_enhanced_validation()

if __name__ == "__main__":
    asyncio.run(main())
