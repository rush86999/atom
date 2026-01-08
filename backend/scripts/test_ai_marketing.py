import asyncio
import os
import sys
import json

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.marketing_manager import AIMarketingManager
from core.reputation_service import ReputationManager
from core.marketing_analytics import PlainEnglishReporter
from integrations.ai_enhanced_service import ai_enhanced_service
from unittest.mock import MagicMock

async def verify_marketing_blueprint():
    print("🚀 Starting Marketing Blueprint Verification...")
    
    # Mock AI calls for deterministic verification
    async def mock_call(*args, **kwargs):
        system_prompt = args[1] if len(args) > 1 else ""
        user_prompt = args[2] if len(args) > 2 else ""
        combined_prompt = f"{system_prompt} {user_prompt}"
        
        if "Analyze this lead" in combined_prompt:
            return {"content": json.dumps({"score": 85, "priority": "HIGH", "rationale": "High intent detected."})}
        if "PUBLIC_REVIEW" in combined_prompt or "PRIVATE_FEEDBACK" in combined_prompt:
            if "fixed the leak" in combined_prompt:
                return {"content": json.dumps({"action": "PUBLIC_REVIEW", "draft": "Thanks! Review us!", "sentiment": "POSITIVE"})}
            else:
                return {"content": json.dumps({"action": "PRIVATE_FEEDBACK", "draft": "Sorry! Tell us more.", "sentiment": "NEGATIVE"})}
        if "Convert these marketing metrics" in combined_prompt:
            return {"content": json.dumps({"content": "Google brought 15 calls. Facebook brought 2. Pivot to Google!"})}
        return {"content": "General AI response"}
    
    ai_enhanced_service._call_openai = mock_call
    
    # Initialize AI service
    await ai_enhanced_service.initialize()
    
    # Initialize services
    marketing = AIMarketingManager(ai_service=ai_enhanced_service)
    reputation = ReputationManager(ai_service=ai_enhanced_service)
    reporter = PlainEnglishReporter(ai_service=ai_enhanced_service)
    
    # 1. Test Lead Scoring
    print("\n--- 1. Testing Lead Scoring ---")
    lead_data = {"email": "test@business.com", "name": "Test Lead", "interest": "Urgent HVAC repair"}
    history = ["Visited pricing page 3 times", "Requested a callback for today"]
    score = await marketing.lead_scoring.calculate_score(lead_data, history)
    print(f"Lead Score: {score}")

    # 2. Test Reputation Strategy
    print("\n--- 2. Testing Reputation Strategy ---")
    positive_interaction = "The technician arrived on time and fixed the leak perfectly. Very happy!"
    negative_interaction = "The technician was late and the price was much higher than the estimate."
    
    pos_strategy = await reputation.determine_feedback_strategy(positive_interaction)
    print(f"Positive Sentiment Action: {pos_strategy.get('action')}")
    print(f"Positive Draft: {pos_strategy.get('draft')}")
    
    neg_strategy = await reputation.determine_feedback_strategy(negative_interaction)
    print(f"Negative Sentiment Action: {neg_strategy.get('action')}")
    print(f"Negative Draft: {neg_strategy.get('draft')}")

    # 3. Test Plain-English Analytics
    print("\n--- 3. Testing Plain-English Analytics ---")
    mock_metrics = {
        "google_search": {"calls": 15, "cost": 150, "clicks": 80},
        "facebook_ads": {"calls": 2, "cost": 100, "clicks": 120}
    }
    report = await reporter.generate_narrative_report(mock_metrics)
    print(f"Narrative Report:\n{report}")
    
    print("\n✅ Marketing Blueprint Verification Complete!")
    await ai_enhanced_service.close()

if __name__ == "__main__":
    asyncio.run(verify_marketing_blueprint())
