import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class ReputationManager:
    """
    Automates review generation and reputation protection.
    """
    
    def __init__(self, ai_service: Any = None):
        self.ai = ai_service

    async def determine_feedback_strategy(self, customer_interaction: str) -> Dict[str, Any]:
        """
        Analyzes customer interaction to decide if we should ask for a public review or private feedback.
        """
        prompt = f"""
        Analyze this customer sentiment:
        "{customer_interaction}"
        
        Decide:
        1. Action: "PUBLIC_REVIEW" or "PRIVATE_FEEDBACK"
        2. Draft: A polite request for the chosen action.
        3. Sentiment: "POSITIVE", "NEUTRAL", or "NEGATIVE"
        
        Format as JSON with keys: action, draft, sentiment.
        """
        
        if self.ai:
            from integrations.ai_enhanced_service import AIRequest, AITaskType, AIModelType, AIServiceType
            request = AIRequest(
                request_id=f"rep_{datetime.now().timestamp()}",
                task_type=AITaskType.CONVERSATION_ANALYSIS,
                model_type=AIModelType.GPT_4O,
                service_type=AIServiceType.OPENAI,
                input_data=prompt
            )
            response = await self.ai.process_ai_request(request)
            return response.output_data
        else:
            return {
                "action": "PUBLIC_REVIEW",
                "draft": "We'd love to hear your feedback!",
                "sentiment": "POSITIVE"
            }

    async def extract_operational_insights(self, reviews: List[str]) -> List[Dict[str, Any]]:
        """
        Extracts "What customers love" and "What to fix" from a list of reviews.
        """
        if not reviews:
            return []
            
        prompt = f"""
        Analyze these customer reviews and extract key operational insights:
        Reviews: {json.dumps(reviews)}
        
        Return a list of insights with:
        - Category (e.g., Service, Pricing, Facility)
        - Sentiment (PRO or CON)
        - Detail (What specifically was mentioned)
        
        Format as a JSON list of objects.
        """
        
        if self.ai:
            from integrations.ai_enhanced_service import AIRequest, AITaskType, AIModelType, AIServiceType
            request = AIRequest(
                request_id=f"insights_{datetime.now().timestamp()}",
                task_type=AITaskType.TOPIC_EXTRACTION,
                model_type=AIModelType.GPT_4O,
                service_type=AIServiceType.OPENAI,
                input_data=prompt
            )
            response = await self.ai.process_ai_request(request)
            return response.output_data if isinstance(response.output_data, list) else []
        else:
            return [{"category": "General", "sentiment": "PRO", "detail": "Customers seem happy overall."}]
