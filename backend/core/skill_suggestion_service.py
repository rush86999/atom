"""
Skill Suggestion Service

AI-powered skill recommendation engine for entity types.
Uses LLMService to analyze entity schemas and suggest relevant skills.
"""
import json
import logging
import re
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from core.models import EntityTypeDefinition, Skill, SkillInstallation
from core.llm_service import LLMService
from core.entity_skill_service import EntitySkillService
from core.skill_suggestion_learning import SkillSuggestionLearning
from core.database import get_db_session

logger = logging.getLogger(__name__)


class SkillSuggestionService:
    """Service for AI-assisted skill suggestions based on entity type schemas.
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        llm_service: Optional[LLMService] = None,
        redis_client: Optional[Any] = None
    ):
        self.db = db
        self.llm_service = llm_service or LLMService(tenant_id="default", db=self.db)
        self.redis_client = redis_client
        self.entity_skill_service = EntitySkillService(db=self.db)

        self._domain_patterns = {
            "email": r'\b(email|e-mail|email_address|mailto)\b',
            "phone": r'\b(phone|telephone|mobile|contact_number|fax)\b',
            "address": r'\b(address|street|city|state|zip|postal|country|location)\b',
            "currency": r'\b(price|cost|amount|total|subtotal|discount|fee|rate|salary|wage|budget)\b',
            "date": r'\b(date|time|timestamp|created|updated|expired|due|start|end)\b',
            "name": r'\b(name|title|first_name|last_name|full_name|customer|vendor|supplier)\b',
            "identifier": r'\b(id|uuid|key|code|reference|number|invoice_id|order_id)\b',
            "url": r'\b(url|uri|link|website|domain|host)\b',
            "file": r'\b(file|document|attachment|image|photo|pdf|csv)\b',
            "status": r'\b(status|state|phase|stage|condition|active|inactive)\b',
            "description": r'\b(description|details|notes|comments|remarks|content|body)\b',
        }

    def analyze_schema(self, json_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract schema features for skill matching."""
        properties = []
        domain_keywords = []
        schema_properties = json_schema.get("properties", {})
        for prop_name, prop_def in schema_properties.items():
            properties.append(prop_name)
            for domain, pattern in self._domain_patterns.items():
                if re.search(pattern, prop_name, re.IGNORECASE):
                    if domain not in domain_keywords:
                        domain_keywords.append(domain)

        return {
            "properties": properties,
            "domain_keywords": domain_keywords,
            "complexity_score": round(len(properties) * 0.1, 2)
        }

    async def suggest_skills_for_entity_type(
        self,
        tenant_id: str,
        entity_type_id: str
    ) -> List[Dict[str, Any]]:
        """Generate AI-powered skill suggestions for an entity type."""
        with get_db_session() as session:
            entity_type = session.query(EntityTypeDefinition).filter(
                EntityTypeDefinition.id == entity_type_id,
                EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.is_active == True
            ).first()

            if not entity_type:
                raise ValueError(f"Entity type '{entity_type_id}' not found")

            # Load available skills
            available_skills = session.query(Skill).all() # Simplified for upstream
            already_attached = set(entity_type.available_skills or [])
            candidate_skills = [s for s in available_skills if s.id not in already_attached]

            if not candidate_skills: return []

            schema_features = self.analyze_schema(entity_type.json_schema)
            prompt = self._build_suggestion_prompt(entity_type.slug, entity_type.display_name, schema_features, candidate_skills)

            try:
                response = await self.llm_service.generate_completion(
                    messages=[
                        {"role": "system", "content": "You are an expert at analyzing data schemas. Respond in JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    model="quality"
                )

                return self._parse_suggestions_response(response.get("content", ""), candidate_skills)
            except Exception as e:
                logger.error(f"Failed to generate skill suggestions: {e}")
                return []

    def _build_suggestion_prompt(self, slug, name, features, skills) -> str:
        skill_desc = "\n".join([f"- {s.name} (ID: {s.id}): {s.description}" for s in skills[:20]])
        return f"""Suggest skills for entity type '{name}' ({slug}).
Properties: {', '.join(features['properties'])}
Available Skills:
{skill_desc}

Respond in JSON: {{"suggestions": [{{"skill_id": "...", "reason": "...", "confidence_score": 0.8}}]}}
"""

    def _parse_suggestions_response(self, response_text, candidate_skills) -> List[Dict[str, Any]]:
        try:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            data = json.loads(json_str)
            suggestions_raw = data.get("suggestions", [])
            skill_map = {s.id: s for s in candidate_skills}
            
            suggestions = []
            for sugg in suggestions_raw[:5]:
                skill_id = sugg.get("skill_id")
                if skill_id in skill_map:
                    suggestions.append({
                        "skill_id": skill_id,
                        "skill_name": skill_map[skill_id].name,
                        "reason": sugg.get("reason", ""),
                        "confidence_score": sugg.get("confidence_score", 0.5)
                    })
            return suggestions
        except Exception:
            return []

    def approve_suggestion(self, tenant_id, entity_type_id, skill_id) -> EntityTypeDefinition:
        """Approve and attach a suggested skill."""
        entity_type = self.entity_skill_service.attach_skill(tenant_id, entity_type_id, skill_id)
        
        # Record feedback
        try:
            learning_service = SkillSuggestionLearning(db=self.db)
            learning_service.record_feedback(
                tenant_id=tenant_id,
                entity_type_id=entity_type_id,
                skill_id=skill_id,
                action="approved"
            )
        except Exception as e:
            logger.warning(f"Failed to record feedback: {e}")
            
        return entity_type


# Global service instance
_default_service: Optional[SkillSuggestionService] = None

def get_skill_suggestion_service(db: Optional[Session] = None) -> SkillSuggestionService:
    if db: return SkillSuggestionService(db=db)
    global _default_service
    if _default_service is None:
        _default_service = SkillSuggestionService()
    return _default_service
