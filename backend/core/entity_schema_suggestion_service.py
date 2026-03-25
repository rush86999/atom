import json
import logging
from typing import Dict, Any, Optional
from core.llm_service import LLMService

logger = logging.getLogger(__name__)

class EntitySchemaSuggestionService:
    """Service for suggesting entity schemas using AI.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService(tenant_id="default")

    async def suggest_schema(self, display_name: str, description: str) -> Dict[str, Any]:
        """Generate a JSON Schema suggestion based on name and description."""
        
        prompt = f"""Generate a JSON Schema for an entity called '{display_name}'.
Description: {description}

The schema must follow these rules:
1. Root type must be 'object'.
2. Include '$schema': 'https://json-schema.org/draft/2020-12/schema'.
3. Define relevant 'properties' with appropriate types (string, number, boolean, array, object).
4. Include a 'required' array for essential fields.
5. Keep it practical and concise (3-7 properties).

Respond ONLY with the raw JSON Schema object.
"""

        try:
            response = await self.llm_service.generate_completion(
                messages=[
                    {"role": "system", "content": "You are an expert data architect. Output only valid JSON Schema."},
                    {"role": "user", "content": prompt}
                ],
                model="quality"
            )

            content = response.get("content", "").strip()
            
            # Clean up potential markdown formatting
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to suggest schema: {e}")
            # Fallback default schema
            return {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"}
                },
                "required": ["name"]
            }

_instance: Optional[EntitySchemaSuggestionService] = None

def get_entity_schema_suggestion_service() -> EntitySchemaSuggestionService:
    global _instance
    if _instance is None:
        _instance = EntitySchemaSuggestionService()
    return _instance
