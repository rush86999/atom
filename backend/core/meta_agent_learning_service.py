from typing import Dict, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func and_, case
from models.entity_type_suggestion import EntityTypeSuggestion, SuggestionLearningRecord
import hashlib
import json

class MetaAgentLearningService:
 """Captures feedback and adjusts suggestion behavior based on user interactions"""

 def __init__(self, db: Session):
 self.db = db

 async def record_feedback(
 self,

 suggestion_id: str,
 feedback_type: str, # approved, rejected, modified
 user_reason: str = None,
 modified_properties: Dict = None
 ) -> Dict:
 """Record user feedback and update learning metrics

 Args:
 tenant_id: Tenant UUID (removed in upstream)
 suggestion_id: Unique suggestion identifier
 feedback_type: Type of feedback (approved/rejected/modified)
 user_reason: Optional user explanation
 modified_properties: Properties user changed (if modified)

 Returns:
 Dict with recorded feedback and quality impact
 """
 # Get the suggestion
 suggestion = self.db.query(EntityTypeSuggestion).filter(
 and_(
 EntityTypeSuggestion
 EntityTypeSuggestion.suggestion_id == suggestion_id
 )
 ).first()

 if not suggestion:
 return {"error": "Suggestion not found", "recorded": False}

 # Calculate pattern signature for learning
 pattern_signature = self._hash_pattern_from_schema(suggestion.json_schema)

 # Create learning record
 learning_record = SuggestionLearningRecord(suggestion_id=suggestion_id,
 feedback_type=feedback_type,
 confidence_at_time=suggestion.confidence,
 pattern_signature=pattern_signature,
 property_overlap=0.0, # Will be calculated asynchronously
 pattern_frequency=1,
 user_reason=user_reason,
 modified_properties=modified_properties,
 created_at=datetime.utcnow()
 )
 self.db.add(learning_record)

 # Update suggestion status
 suggestion.status = feedback_type
 suggestion.feedback = user_reason
 suggestion.reviewed_at = datetime.utcnow()

 self.db.commit()

 # Calculate quality impact
 quality_impact = self._calculate_quality_impact("default", pattern_signature)

 return {
 "recorded": True,
 "suggestion_id": suggestion_id,
 "feedback_type": feedback_type,
 "quality_impact": quality_impact
 }

 def calculate_suggestion_quality(
 self,

 days: int = 30
 ) -> Dict:
 """Calculate quality metrics for recent suggestions

 Args:
 tenant_id: Tenant UUID (removed in upstream)
 days: Number of days to look back

 Returns:
 Dict with quality metrics including approval rates, pattern performance
 """
 cutoff_date = datetime.utcnow() - timedelta(days=days)

 # Total suggestions in period
 total_suggestions = self.db.query(func.count(EntityTypeSuggestion.id)).filter(
 and_(
 EntityTypeSuggestion
 EntityTypeSuggestion.created_at >= cutoff_date
 )
 ).scalar()

 # Approval/rejection counts
 feedback_counts = self.db.query(
 EntityTypeSuggestion.status,
 func.count(EntityTypeSuggestion.id)
 ).filter(
 and_(
 EntityTypeSuggestion
 EntityTypeSuggestion.created_at >= cutoff_date,
 EntityTypeSuggestion.status.in_(['approved', 'rejected', 'modified'])
 )
 ).group_by(EntityTypeSuggestion.status).all()

 counts = {status: count for status, count in feedback_counts}
 approval_count = counts.get('approved', 0)
 total_decisions = sum(counts.values())

 # Overall approval rate
 approval_rate = approval_count / total_decisions if total_decisions > 0 else 0.0

 # Pattern-specific approval rates
 pattern_rates = self._calculate_pattern_approval_rates("default", cutoff_date)

 # Confidence calibration (predicted vs actual)
 calibration = self._calculate_confidence_calibration("default", cutoff_date)

 return {
 
 "period_days": days,
 "total_suggestions": total_suggestions,
 "total_decisions": total_decisions,
 "approval_count": approval_count,
 "rejection_count": counts.get('rejected', 0),
 "modified_count": counts.get('modified', 0),
 "approval_rate": approval_rate,
 "pattern_approval_rates": pattern_rates,
 "confidence_calibration": calibration
 }

 def adjust_confidence(
 self,
 pattern_signature: str,
 feedback_type: str,
 current_confidence: float
 ) -> float:
 """Adjust confidence based on feedback

 Args:
 pattern_signature: Hash of pattern properties
 feedback_type: Type of feedback received
 current_confidence: Current confidence score (0-1)

 Returns:
 Adjusted confidence score (0-1)
 """
 if feedback_type == 'approved':
 # Boost confidence for approved patterns
 adjustment = 0.1
 return min(0.95, current_confidence + adjustment)
 elif feedback_type == 'rejected':
 # Reduce confidence for rejected patterns
 adjustment = 0.2
 return max(0.1, current_confidence - adjustment)
 elif feedback_type == 'modified':
 # Slight boost (user saw value, just needed tweaks)
 adjustment = 0.05
 return min(0.9, current_confidence + adjustment)

 return current_confidence

 def get_learning_insights(
 self) -> Dict:
 """Get learning progress and insights

 Args:
 tenant_id: Tenant UUID (removed in upstream)

 Returns:
 Dict with learning insights including progress, top patterns, calibration
 """
 # Get 30-day quality metrics
 quality = self.calculate_suggestion_quality(days=30)

 # Get top performing patterns
 top_patterns = self._get_top_patterns(limit=5)

 # Get learning progress over time
 progress = self._get_learning_progress("default")

 return {
 
 "total_suggestions": quality['total_suggestions'],
 "approval_rate": quality['approval_rate'],
 "top_approved_patterns": top_patterns,
 "confidence_calibration": quality['confidence_calibration'],
 "learning_progress": progress
 }

 def _hash_pattern_from_schema(self, json_schema: Dict) -> str:
 """Create stable hash from schema properties"""
 # Extract property keys for hashing
 properties = json_schema.get('properties', {})
 property_keys = sorted(properties.keys())

 # Create hash from sorted keys
 hash_input = json.dumps(property_keys, sort_keys=True)
 return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

 def _calculate_quality_impact(self, pattern_signature: str) -> str:
 """Calculate the impact of this feedback on quality"""
 quality = self.calculate_suggestion_quality(days=30)
 pattern_rate = quality['pattern_approval_rates'].get(pattern_signature, 0.5)

 if pattern_rate > 0.8:
 return "high_approval_pattern"
 elif pattern_rate < 0.3:
 return "low_approval_pattern"
 else:
 return "neutral"

 def _calculate_pattern_approval_rates(self, cutoff_date: datetime) -> Dict[str, float]:
 """Calculate approval rate per pattern signature"""
 # Get all feedback for patterns in period
 pattern_stats = self.db.query(
 SuggestionLearningRecord.pattern_signature,
 func.count(SuggestionLearningRecord.id).label('total'),
 func.sum(case([(SuggestionLearningRecord.feedback_type == 'approved', 1)], else_=0)).label('approved')
 ).filter(
 and_(
 SuggestionLearningRecord
 SuggestionLearningRecord.created_at >= cutoff_date
 )
 ).group_by(SuggestionLearningRecord.pattern_signature).all()

 approval_rates = {}
 for pattern_sig, total, approved in pattern_stats:
 if total > 0:
 approval_rates[pattern_sig] = approved / total

 return approval_rates

 def _calculate_confidence_calibration(self, cutoff_date: datetime) -> Dict:
 """Calculate how well confidence scores predict actual acceptance"""
 # Get all learning records with confidence data
 records = self.db.query(SuggestionLearningRecord).filter(
 and_(
 SuggestionLearningRecord
 SuggestionLearningRecord.created_at >= cutoff_date
 )
 ).all()

 if not records:
 return {"avg_confidence": 0.0, "actual_approval_rate": 0.0, "calibration_error": 0.0}

 # Calculate average confidence vs actual approval
 total_confidence = sum(r.confidence_at_time for r in records)
 avg_confidence = total_confidence / len(records)

 approved_count = sum(1 for r in records if r.feedback_type == 'approved')
 actual_approval_rate = approved_count / len(records)

 # Calibration error: difference between predicted and actual
 calibration_error = abs(avg_confidence - actual_approval_rate)

 return {
 "avg_confidence": round(avg_confidence, 3),
 "actual_approval_rate": round(actual_approval_rate, 3),
 "calibration_error": round(calibration_error, 3)
 }

 def _get_top_patterns(self, limit: int = 5) -> List[Dict]:
 """Get top performing patterns by approval rate"""
 cutoff_date = datetime.utcnow() - timedelta(days=30)

 patterns = self.db.query(
 SuggestionLearningRecord.pattern_signature,
 func.count(SuggestionLearningRecord.id).label('total'),
 func.sum(case([(SuggestionLearningRecord.feedback_type == 'approved', 1)], else_=0)).label('approved')
 ).filter(
 and_(
 SuggestionLearningRecord
 SuggestionLearningRecord.created_at >= cutoff_date,
 SuggestionLearningRecord.pattern_signature.isnot(None)
 )
 ).group_by(SuggestionLearningRecord.pattern_signature).all()

 # Sort by approval rate
 pattern_list = []
 for pattern_sig, total, approved in patterns:
 if total >= 2: # Only include patterns with at least 2 occurrences
 approval_rate = approved / total
 pattern_list.append({
 "pattern_signature": pattern_sig,
 "approval_rate": round(approval_rate, 3),
 "total_occurrences": total
 })

 pattern_list.sort(key=lambda x: x['approval_rate'], reverse=True)
 return pattern_list[:limit]

 def _get_learning_progress(self) -> Dict:
 """Track learning progress over time"""
 # Compare last 7 days to previous 7 days
 recent_cutoff = datetime.utcnow() - timedelta(days=7)
 previous_cutoff = datetime.utcnow() - timedelta(days=14)

 # Recent period
 recent_quality = self.calculate_suggestion_quality(days=7)
 recent_rate = recent_quality['approval_rate']

 # Previous period
 previous_quality = self.db.query(
 func.count(SuggestionLearningRecord.id)
 ).filter(
 and_(
 SuggestionLearningRecord
 SuggestionLearningRecord.created_at >= previous_cutoff,
 SuggestionLearningRecord.created_at < recent_cutoff
 )
 ).scalar()

 # Calculate improvement
 improvement = 0.0
 if previous_quality and previous_quality > 0:
 # This is simplified - in production would compare actual rates
 improvement = recent_rate * 0.1 # Assume 10% improvement for now

 return {
 "recent_approval_rate": round(recent_rate, 3),
 "improvement_trend": round(improvement, 3),
 "learning_stage": "improving" if improvement > 0.05 else "stable"
 }
