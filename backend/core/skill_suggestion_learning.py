"""
Skill Suggestion Learning Service

Learns from user feedback on skill suggestions to improve future recommendations.
Tracks approved/rejected patterns and enables auto-binding for high-confidence suggestions.
"""
import hashlib
import json
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from core.models import (
    SkillSuggestionFeedback,
    EntityTypeDefinition,
    Skill
)
from core.database import get_db_session
from core.entity_skill_service import EntitySkillService

logger = logging.getLogger(__name__)


class SkillSuggestionLearning:
    """Service for learning from skill suggestion feedback.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.entity_skill_service = EntitySkillService(db=self.db)

    def record_feedback(
        self,
        tenant_id: str,
        entity_type_id: str,
        skill_id: str,
        action: str,
        confidence_score: Optional[float] = None,
        schema_features: Optional[Dict[str, Any]] = None
    ) -> SkillSuggestionFeedback:
        """
        Record user feedback on a skill suggestion.
        """
        with get_db_session() as session:
            # Validate action
            valid_actions = ['approved', 'rejected', 'dismissed']
            if action not in valid_actions:
                raise ValueError(f"Invalid action '{action}'")

            # Load entity type
            entity_type = session.query(EntityTypeDefinition).filter(
                EntityTypeDefinition.id == entity_type_id,
                EntityTypeDefinition.tenant_id == tenant_id,
                EntityTypeDefinition.is_active == True
            ).first()

            if not entity_type:
                raise ValueError(f"Entity type '{entity_type_id}' not found")

            # Extract features if not provided
            if not schema_features:
                schema_features = self._extract_schema_features(entity_type.json_schema)

            # Calculate hash
            schema_hash = self._calculate_schema_hash(entity_type.json_schema)

            # Create record
            feedback = SkillSuggestionFeedback(
                tenant_id=tenant_id,
                entity_type_id=entity_type_id,
                skill_id=skill_id,
                schema_features=schema_features,
                schema_hash=schema_hash,
                action=action,
                confidence_score=confidence_score
            )

            try:
                session.add(feedback)
                session.commit()
                session.refresh(feedback)
                
                # Update quality
                self.calculate_suggestion_quality(skill_id, session)

                return feedback
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to record feedback: {e}")
                raise

    def get_learned_patterns(
        self,
        tenant_id: str,
        min_confidence: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Extract successful patterns from approved suggestions."""
        with get_db_session() as session:
            feedback_records = session.query(SkillSuggestionFeedback).filter(
                SkillSuggestionFeedback.tenant_id == tenant_id
            ).all()

            patterns = {}
            for feedback in feedback_records:
                key = (feedback.schema_hash, feedback.skill_id)
                if key not in patterns:
                    patterns[key] = {
                        "schema_hash": feedback.schema_hash,
                        "skill_id": feedback.skill_id,
                        "approved": 0,
                        "total": 0,
                        "schema_features": feedback.schema_features
                    }
                if feedback.action == "approved":
                    patterns[key]["approved"] += 1
                patterns[key]["total"] += 1

            learned_patterns = []
            for pattern in patterns.values():
                approval_rate = pattern["approved"] / pattern["total"]
                if approval_rate >= min_confidence and pattern["total"] >= 2:
                    learned_patterns.append({
                        "schema_hash": pattern["schema_hash"],
                        "skill_id": pattern["skill_id"],
                        "approval_rate": round(approval_rate, 2),
                        "count": pattern["total"],
                        "schema_features": pattern["schema_features"]
                    })
            return learned_patterns

    def calculate_suggestion_quality(self, skill_id: str, session: Session) -> Optional[float]:
        """Update suggestion quality scores for a skill."""
        feedback_records = session.query(SkillSuggestionFeedback).filter(
            SkillSuggestionFeedback.skill_id == skill_id
        ).all()

        if not feedback_records:
            return None

        total_quality = 0.0
        for feedback in feedback_records:
            usage_factor = (feedback.usage_count + 1) ** 0.5 / 10.0
            
            # Simplified approval rate for current session
            pattern_feedback = [f for f in feedback_records if f.schema_hash == feedback.schema_hash]
            approved_count = sum(1 for f in pattern_feedback if f.action == "approved")
            approval_rate = approved_count / len(pattern_feedback)
            
            quality = approval_rate * usage_factor
            feedback.suggestion_quality = quality
            total_quality += quality

        try:
            session.commit()
            return total_quality / len(feedback_records)
        except Exception:
            session.rollback()
            return None

    def _extract_schema_features(self, json_schema: Dict[str, Any]) -> Dict[str, Any]:
        properties = json_schema.get("properties", {})
        property_names = list(properties.keys())
        return {
            "properties": property_names,
            "property_count": len(property_names)
        }

    def _calculate_schema_hash(self, json_schema: Dict[str, Any]) -> str:
        schema_str = json.dumps(json_schema, sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()

    def _calculate_schema_similarity(
        self,
        features1: Dict[str, Any],
        features2: Dict[str, Any]
    ) -> float:
        props1 = set(features1.get("properties", []))
        props2 = set(features2.get("properties", []))
        if not props1 and not props2: return 1.0
        intersection = props1 & props2
        union = props1 | props2
        return len(intersection) / len(union) if union else 0


def get_skill_suggestion_learning_service(db: Optional[Session] = None) -> SkillSuggestionLearning:
    return SkillSuggestionLearning(db=db)
