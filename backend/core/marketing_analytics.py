import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class PlainEnglishReporter:
    """
    Converts complex marketing metrics into simple narrative reports.
    """
    
    def __init__(self, ai_service: Any = None):
        self.ai = ai_service

    async def generate_narrative_report(self, metrics_data: Dict[str, Any]) -> str:
        """
        Takes raw metrics (calls, clicks, spend) and produces a 3-4 sentence plain English report.
        """
        prompt = f"""
        Convert these marketing metrics into a simple, non-technical report for a small business owner:
        Metrics: {json.dumps(metrics_data)}
        
        The report should answer:
        1. Where did leads come from?
        2. What was the most successful channel?
        3. Simple advice for next week.
        
        Avoid technical jargon like "CTR", "CPC", or "ROAS". Use "Calls", "Clicks", and "Value".
        """
        
        if self.ai:
            from integrations.ai_enhanced_service import AIRequest, AITaskType, AIModelType, AIServiceType
            request = AIRequest(
                request_id=f"report_{datetime.now().timestamp()}",
                task_type=AITaskType.CONTENT_GENERATION,
                model_type=AIModelType.GPT_4O,
                service_type=AIServiceType.OPENAI,
                input_data=prompt
            )
            response = await self.ai.process_ai_request(request)
            output = response.output_data
            if isinstance(output, dict):
                return output.get('content') or str(output)
            return str(output)

        else:
            return "Marketing is performing well. Google and Facebook are both bringing in new leads."

    async def get_budget_advice(self, performance_by_channel: Dict[str, Dict[str, Any]]) -> str:
        """
        Suggests budget reallocations based on ROI signals.
        """
        prompt = f"""
        Analyze the performance of these marketing channels and suggest where to put more or less money:
        Performance: {json.dumps(performance_by_channel)}
        
        Provide 1-2 practical recommendations.
        """
        
        if self.ai:
            from integrations.ai_enhanced_service import AIRequest, AITaskType, AIModelType, AIServiceType
            request = AIRequest(
                request_id=f"advice_{datetime.now().timestamp()}",
                task_type=AITaskType.CONTENT_GENERATION,
                model_type=AIModelType.GPT_4O,
                service_type=AIServiceType.OPENAI,
                input_data=prompt
            )
            response = await self.ai.process_ai_request(request)
            output = response.output_data
            if isinstance(output, dict):
                return output.get('content') or str(output)
            return str(output)
        else:
            return "Consider increasing Google Search budget based on current call volume."
