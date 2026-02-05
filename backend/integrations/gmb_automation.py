from datetime import datetime, timedelta
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class GMBAutomation:
    """
    Automates Google Business Profile (formerly GMB) updates and interactions.
    """
    
    def __init__(self, ai_service: Any = None):
        self.ai = ai_service

    async def generate_weekly_update(self, business_info: Dict[str, Any], recent_events: List[str]) -> str:
        """
        Generates a localized, SEO-optimized post for Google Business Profile.
        """
        prompt = f"""
        Generate a Google Business Profile (GMB) post for: {business_info['name']}
        Location: {business_info['location']}
        Recent Business Events/Offers: {", ".join(recent_events)}
        
        The post should be engaging, include a call to action, and use local keywords to optimize for 'near me' searches.
        Keep it professional yet friendly.
        """
        
        if self.ai:
            from integrations.ai_enhanced_service import (
                AIModelType,
                AIRequest,
                AIServiceType,
                AITaskType,
            )
            request = AIRequest(
                request_id=f"gmb_{datetime.now().timestamp()}",
                task_type=AITaskType.CONTENT_GENERATION,
                model_type=AIModelType.GPT_4O,
                service_type=AIServiceType.OPENAI,
                input_data=prompt
            )
            response = await self.ai.process_ai_request(request)
            return response.output_data['content'] if isinstance(response.output_data, dict) else str(response.output_data)
        else:
            return f"Auto-generated post for {business_info['name']}: Check out our latest services in {business_info['location']}!"

    async def draft_review_response(self, review_text: str, rating: int) -> str:
        """
        Drafts a response to a customer review with appropriate guardrails.
        """
        prompt = f"""
        Draft a response to this {rating}-star review:
        "{review_text}"
        
        If the rating is low (1-2), be empathetic and offer to resolve privately.
        If high (4-5), express gratitude and mention a specific detail if possible.
        """
        
        if self.ai:
            from integrations.ai_enhanced_service import (
                AIModelType,
                AIRequest,
                AIServiceType,
                AITaskType,
            )
            request = AIRequest(
                request_id=f"review_{datetime.now().timestamp()}",
                task_type=AITaskType.CONTENT_GENERATION,
                model_type=AIModelType.GPT_4O,
                service_type=AIServiceType.OPENAI,
                input_data=prompt
            )
            response = await self.ai.process_ai_request(request)
            return response.output_data['content'] if isinstance(response.output_data, dict) else str(response.output_data)
        else:
            return "Thank you for your feedback! We appreciate your business."
