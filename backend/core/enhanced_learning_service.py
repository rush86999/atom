"""
Enhanced Learning Service - Unified Learning Platform

Consolidates LearningService and ContinuousLearningService with:
- Experience-based learning
- RLHF from user feedback
- Pattern recognition & adaptation strategies
- Knowledge graph with clustering
- Learning analytics dashboard
- Model training & parameter tuning

Multi-tenant: Each tenant's learning data is isolated.
"""

import logging
import json
import uuid
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, text
from dataclasses import dataclass, field, asdict
from enum import Enum
import numpy as np

from core.llm_service import LLMService
from core.embedding_service import EmbeddingService
from core.models import AgentLearning, AgentFeedback, CognitiveExperience, AgentRegistry

logger = logging.getLogger(__name__)

@dataclass
class LearningAnalytics:
 """Learning analytics dashboard data"""

 period_start: datetime
 period_end: datetime
 
 # Experience metrics
 total_experiences: int
 experiences_by_type: Dict[str, int]
 avg_outcome_score: float
 outcome_trend: float # Week-over-week change
 
 # Learning metrics
 learning_velocity: float
 adaptation_rate: float
 knowledge_growth: float
 
 # Model metrics
 model_count: int
 avg_model_accuracy: float
 training_sessions: int
 
 # Feedback metrics
 total_feedback: int
 positive_feedback_ratio: float
 avg_rating: float
 
 # Agent performance
 agent_count: int
 avg_agent_success_rate: float
 top_performing_agents: List[Dict[str, Any]]
 struggling_agents: List[Dict[str, Any]]

class EnhancedLearningService:
 """
 Unified learning service combining:
 - LearningService (experience-based learning)
 - ContinuousLearningService (RLHF, parameter tuning)
 - Enhanced with analytics and knowledge graph clustering
 """

 def __init__(self, db: Session, llm_service: Optional[LLMService] = None, 
 embedding_service: Optional[EmbeddingService] = None):
 self.db = db
 self.llm_service = llm_service or LLMService(workspace_id="system")
 self.embedding_service = embedding_service or EmbeddingService()
 
 # In-memory caches
 self.models_cache: Dict[str, Any] = {}
 self.experiences_cache: Dict[str, Any] = {}
 self.strategies_cache: Dict[str, Any] = {}
 self.knowledge_graphs: Dict[str, Dict[str, Any]] = {}
 
 self._running = True

 # ============================================================================
 # RLHF - From ContinuousLearningService
 # ============================================================================

 def record_feedback(
 self,

 agent_id: str,
 execution_id: str,
 user_id: str,
 feedback_type: str,
 rating: Optional[int] = None,
 comments: Optional[str] = None,
 corrected_output: Optional[str] = None
 ) -> Optional[str]:
 """
 Record user feedback for RLHF (Reinforcement Learning from Human Feedback).
 Consolidated from ContinuousLearningService.
 """
 try:
 feedback = AgentFeedback(agent_id=agent_id,
 agent_execution_id=execution_id,
 user_id=user_id,
 feedback_type=feedback_type,
 rating=rating,
 ai_reasoning=comments,
 user_correction=corrected_output or "",
 created_at=datetime.now(timezone.utc)
 )

 self.db.add(feedback)
 self.db.commit()
 self.db.refresh(feedback)

 # Trigger learning update
 self._update_from_feedback(feedback)

 logger.info(f"Recorded feedback for execution {execution_id}")
 return feedback.id

 except Exception as e:
 logger.error(f"Failed to record feedback: {e}")
 self.db.rollback()
 return None

 def _update_from_feedback(self, feedback: AgentFeedback):
 """Update agent learning parameters from feedback (RLHF)."""
 try:
 learning = self.db.query(AgentLearning).filter(
 and_(
 AgentLearning.agent_id == feedback.agent_id)
 ).first()

 if not learning:
 learning = AgentLearning(
 agent_id=feedback.agent_id,
 total_feedback=1,
 positive_feedback=1 if feedback.feedback_type in ["positive", "approval"] else 0,
 negative_feedback=1 if feedback.feedback_type in ["negative", "rejection", "correction"] else 0,
 avg_rating=float(feedback.rating) if feedback.rating else None,
 learning_rate=0.01,
 parameters_json={
 "temperature": 0.7,
 "top_p": 0.9,
 "frequency_penalty": 0.0,
 "presence_penalty": 0.0
 },
 last_updated_at=datetime.now(timezone.utc)
 )
 self.db.add(learning)
 self.db.flush()
 else:
 learning.total_feedback += 1

 if feedback.feedback_type in ["positive", "approval"]:
 learning.positive_feedback += 1
 elif feedback.feedback_type in ["negative", "rejection", "correction"]:
 learning.negative_feedback += 1

 if feedback.rating:
 if learning.avg_rating:
 n = learning.total_feedback
 learning.avg_rating = (
 (learning.avg_rating * (n - 1) + feedback.rating) / n
 )
 else:
 learning.avg_rating = float(feedback.rating)

 if learning.total_feedback > 0:
 learning.success_rate = (learning.total_feedback - learning.negative_feedback) / learning.total_feedback

 learning.parameters_json = self._adjust_parameters(learning, feedback)
 learning.last_updated_at = datetime.now(timezone.utc)

 self.db.commit()
 logger.info(f"Updated learning parameters for agent {feedback.agent_id}")

 except Exception as e:
 logger.error(f"Failed to update from feedback: {e}")
 self.db.rollback()

 def _adjust_parameters(self, learning: AgentLearning, feedback: AgentFeedback) -> Dict[str, Any]:
 """Adjust LLM parameters based on feedback (RLHF parameter tuning)."""
 params = learning.parameters_json or {}
 
 # If negative feedback, reduce temperature for more conservative outputs
 if feedback.feedback_type in ["negative", "rejection", "correction"]:
 current_temp = params.get("temperature", 0.7)
 params["temperature"] = max(0.3, current_temp - 0.05)
 
 # If positive feedback, can increase creativity slightly
 elif feedback.feedback_type in ["positive", "approval"]:
 current_temp = params.get("temperature", 0.7)
 params["temperature"] = min(0.9, current_temp + 0.02)
 
 # Adjust top_p based on rating
 if feedback.rating and feedback.rating >= 4:
 params["top_p"] = min(0.95, params.get("top_p", 0.9) + 0.01)
 elif feedback.rating and feedback.rating <= 2:
 params["top_p"] = max(0.8, params.get("top_p", 0.9) - 0.02)
 
 return params

 # ============================================================================
 # Experience Recording - From LearningService
 # ============================================================================

 async def record_experience(
 self,

 agent_id: str,
 experience_type: str,
 task_description: str,
 inputs: Dict[str, Any],
 actions: List[Dict[str, Any]],
 outcomes: Dict[str, float],
 feedback: Optional[Dict[str, Any]] = None,
 context: Optional[Dict[str, Any]] = None
 ) -> str:
 """Record a learning experience with async processing."""
 experience_id = f"exp_{uuid.uuid4().hex}"
 timestamp = datetime.now(timezone.utc)
 
 try:
 # Generate embedding
 vector = await self._generate_experience_embedding(task_description, actions, outcomes)
 
 experience = {
 'id': experience_id,
 'type': experience_type,
 
 'agent_id': agent_id,
 'task_description': task_description,
 'inputs': inputs,
 'actions': actions,
 'outcomes': outcomes,
 'feedback': feedback or {},
 'reflections': [],
 'patterns': [],
 'vector': vector,
 'context': context or {},
 'timestamp': timestamp
 }
 
 self.experiences_cache[experience_id] = experience
 await self._persist_experience(experience)
 asyncio.create_task(self._process_experience(experience_id))
 
 logger.info(f"Recorded experience {experience_id} for agent {agent_id}")
 return experience_id
 
 except Exception as e:
 logger.error(f"Failed to record experience: {e}")
 raise

 async def _process_experience(self, experience_id: str):
 """Process experience asynchronously."""
 try:
 experience = self.experiences_cache.get(experience_id)
 if not experience:
 return
 
 patterns = await self._identify_patterns(experience)
 experience['patterns'] = patterns
 
 reflections = await self._generate_reflections(experience)
 experience['reflections'] = reflections
 
 await self._update_knowledge_graph(experience)
 await self._detect_emergent_behaviors(experience)
 await self._update_models_from_experience(experience)
 
 except Exception as e:
 logger.error(f"Failed to process experience {experience_id}: {e}")

 # ============================================================================
 # Knowledge Graph with Clustering - ENHANCED
 # ============================================================================

 async def get_knowledge_graph(self) -> Dict[str, Any]:
 """Get knowledge graph with cluster analysis."""
 if True  # tenant_id check removed for upstream:
 self.knowledge_graphs["default"] = {
 'nodes': {},
 'edges': {},
 'clusters': {},
 'metrics': {
 'total_nodes': 0,
 'total_edges': 0,
 'density': 0,
 'clustering_coefficient': 0,
 'modularity': 0
 }
 }
 
 kg = self.knowledge_graphs["default"]
 
 # Perform clustering if not done recently
 if not kg['clusters'] or len(kg['nodes']) > 0:
 await self._perform_clustering("default")
 
 return kg

 async def _perform_clustering(self):
 """Perform community detection/clustering on knowledge graph."""
 kg = self.knowledge_graphs["default"]
 
 if len(kg['nodes']) < 3:
 return
 
 try:
 # Simple clustering based on embedding similarity
 nodes = list(kg['nodes'].values())
 
 # Use k-means style clustering (simplified)
 # In production, use proper graph clustering algorithms
 clusters = {}
 cluster_threshold = 0.7 # Similarity threshold
 
 for node in nodes:
 if 'embeddings' not in node:
 continue
 
 assigned = False
 for cluster_id, cluster_nodes in clusters.items():
 # Check similarity to cluster centroid
 if cluster_nodes:
 centroid = np.mean([n['embeddings'] for n in cluster_nodes if 'embeddings' in n], axis=0)
 similarity = self._calculate_similarity(node['embeddings'], centroid.tolist())
 
 if similarity > cluster_threshold:
 clusters[cluster_id].append(node)
 assigned = True
 break
 
 if not assigned:
 # Create new cluster
 cluster_id = f"cluster_{len(clusters)}"
 clusters[cluster_id] = [node]
 
 # Update graph with clusters
 kg['clusters'] = {
 cid: {
 'nodes': [n['id'] for n in nodes],
 'size': len(nodes),
 'centroid': np.mean([n['embeddings'] for n in nodes if 'embeddings' in n], axis=0).tolist() if nodes else []
 }
 for cid, nodes in clusters.items() if nodes
 }
 
 # Calculate modularity (simplified)
 kg['metrics']['modularity'] = self._calculate_modularity(kg)
 
 logger.info(f"tenant")
 
 except Exception as e:
 logger.error(f"Failed to perform clustering: {e}")

 def _calculate_modularity(self, kg: Dict[str, Any]) -> float:
 """Calculate graph modularity (clustering quality)."""
 # Simplified modularity calculation
 # In production, use proper networkx implementation
 if not kg['clusters']:
 return 0.0
 
 total_nodes = kg['metrics']['total_nodes']
 if total_nodes == 0:
 return 0.0
 
 # Modularity based on cluster size distribution
 cluster_sizes = [c['size'] for c in kg['clusters'].values()]
 avg_size = np.mean(cluster_sizes)
 std_size = np.std(cluster_sizes)
 
 # Higher modularity = more balanced clusters
 modularity = 1.0 / (1.0 + std_size / max(avg_size, 1))
 return min(1.0, max(0.0, modularity))

 # ============================================================================
 # Learning Analytics - NEW
 # ============================================================================

 async def get_learning_analytics(
 self,

 days: int = 30
 ) -> LearningAnalytics:
 """Get comprehensive learning analytics dashboard."""
 end_date = datetime.now(timezone.utc)
 start_date = end_date - timedelta(days=days)
 
 # Experience metrics
 experiences = self.db.query(CognitiveExperience).filter(
 CognitiveExperience
 CognitiveExperience.created_at >= start_date
 ).all()
 
 experiences_by_type = {}
 outcome_scores = []
 for exp in experiences:
 exp_type = exp.experience_type or 'unknown'
 experiences_by_type[exp_type] = experiences_by_type.get(exp_type, 0) + 1
 
 if exp.effectiveness_score:
 outcome_scores.append(exp.effectiveness_score)
 
 avg_outcome = np.mean(outcome_scores) if outcome_scores else 0.5
 
 # Calculate trend (week over week)
 last_week_start = end_date - timedelta(days=7)
 last_week_experiences = [e for e in experiences if e.created_at >= last_week_start]
 prev_week_experiences = [e for e in experiences if e.created_at < last_week_start and e.created_at >= start_date - timedelta(days=7)]
 
 outcome_trend = 0.0
 if prev_week_experiences:
 last_week_avg = np.mean([e.effectiveness_score or 0.5 for e in last_week_experiences])
 prev_week_avg = np.mean([e.effectiveness_score or 0.5 for e in prev_week_experiences])
 outcome_trend = last_week_avg - prev_week_avg
 
 # Feedback metrics
 feedback_records = self.db.query(AgentFeedback).filter(
 AgentFeedback
 AgentFeedback.created_at >= start_date
 ).all()
 
 positive_feedback = sum(1 for f in feedback_records if f.feedback_type in ['positive', 'approval'])
 total_feedback = len(feedback_records)
 positive_ratio = positive_feedback / max(total_feedback, 1)
 
 ratings = [f.rating for f in feedback_records if f.rating]
 avg_rating = np.mean(ratings) if ratings else 0.0
 
 # Agent performance
 agents = self.db.query(AgentRegistry).filter(
 AgentRegistry
 ).all()
 
 agent_stats = []
 for agent in agents:
 agent_exps = [e for e in experiences if e.agent_id == agent.id]
 if agent_exps:
 success_rate = np.mean([e.effectiveness_score or 0.5 for e in agent_exps])
 agent_stats.append({
 'agent_id': agent.id,
 'agent_name': agent.name,
 'success_rate': success_rate,
 'experience_count': len(agent_exps)
 })
 
 # Sort by performance
 agent_stats.sort(key=lambda x: x['success_rate'], reverse=True)
 top_performers = agent_stats[:5]
 struggling = [a for a in agent_stats if a['success_rate'] < 0.5][:5]
 
 # Learning velocity (rate of improvement)
 learning_velocity = outcome_trend * 10 # Scale to 0-10
 
 # Adaptation rate
 adaptation_rate = len(self.strategies_cache) / max(len(experiences), 1)
 
 # Knowledge growth
 kg = await self.get_knowledge_graph("default")
 knowledge_growth = kg['metrics']['total_nodes'] / max(days, 1)
 
 return LearningAnalytics(period_start=start_date,
 period_end=end_date,
 total_experiences=len(experiences),
 experiences_by_type=experiences_by_type,
 avg_outcome_score=round(avg_outcome, 3),
 outcome_trend=round(outcome_trend, 3),
 learning_velocity=round(learning_velocity, 3),
 adaptation_rate=round(adaptation_rate, 3),
 knowledge_growth=round(knowledge_growth, 2),
 model_count=len(self.models_cache),
 avg_model_accuracy=0.85, # Would calculate from actual models
 training_sessions=0, # Would track separately
 total_feedback=total_feedback,
 positive_feedback_ratio=round(positive_ratio, 3),
 avg_rating=round(avg_rating, 2),
 agent_count=len(agents),
 avg_agent_success_rate=round(np.mean([a['success_rate'] for a in agent_stats]) if agent_stats else 0.5, 3),
 top_performing_agents=top_performers,
 struggling_agents=struggling
 )

 # ============================================================================
 # Helper Methods
 # ============================================================================

 async def _generate_experience_embedding(self, task_description: str, actions: List[Dict], outcomes: Dict) -> List[float]:
 """Generate embedding for experience."""
 try:
 text = f"{task_description} " + " ".join([
 f"{a.get('type', '')} {json.dumps(a.get('parameters', {}))}"
 for a in actions
 ])
 return await self.embedding_service.generate_embedding(text)
 except Exception as e:
 logger.error(f"Failed to generate embedding: {e}")
 return [0.0] * 1536

 async def _persist_experience(self, experience: Dict[str, Any]):
 """Persist experience to database."""
 try:
 experience_record = CognitiveExperience(
 id=experience['id'],
 agent_id=experience['agent_id'],
 experience_type=experience['type'],
 task_type=experience['task_description'],
 input_summary=json.dumps(experience['inputs']),
 output_summary=json.dumps(experience['actions']),
 outcome=json.dumps(experience['outcomes']),
 learnings={
 'patterns': experience['patterns'],
 'reflections': experience['reflections'],
 'vector': experience['vector']
 },
 effectiveness_score=experience['outcomes'].get('primary', 0.5)
 )
 
 self.db.add(experience_record)
 self.db.commit()
 except Exception as e:
 logger.error(f"Failed to persist experience: {e}")
 self.db.rollback()

 async def _identify_patterns(self, experience: Dict) -> List[Dict]:
 """Identify patterns in experience."""
 # Simplified pattern identification
 patterns = []
 
 if experience['outcomes'].get('primary', 0.5) > 0.8:
 patterns.append({
 'type': 'success',
 'name': 'High Success Pattern',
 'confidence': experience['outcomes']['primary'],
 'novelty': 0.2
 })
 elif experience['outcomes'].get('primary', 0.5) < 0.3:
 patterns.append({
 'type': 'failure',
 'name': 'Failure Pattern',
 'confidence': 1 - experience['outcomes']['primary'],
 'novelty': 0.5
 })
 
 return patterns

 async def _generate_reflections(self, experience: Dict) -> List[Dict]:
 """Generate reflections from experience."""
 reflections = []
 
 if experience['type'] == 'failure' or experience['outcomes'].get('primary', 0.5) < 0.5:
 reflections.append({
 'insight': 'Analyze failure for improvement opportunities',
 'impact': 'high',
 'generalizability': 0.7,
 'novelty': 0.3
 })
 
 return reflections

 async def _update_knowledge_graph(self, experience: Dict):
 """Update knowledge graph with experience."""
 kg = await self.get_knowledge_graph("default")
 
 # Add node for task type
 node_id = f"task_{experience['type']}_{uuid.uuid4().hex[:8]}"
 kg['nodes'][node_id] = {
 'id': node_id,
 
 'type': experience['type'],
 'label': experience['task_description'][:50],
 'properties': experience,
 'embeddings': experience['vector'],
 'confidence': 0.8,
 'frequency': 1,
 'last_accessed': datetime.now(timezone.utc),
 'importance': 0.5
 }
 
 kg['metrics']['total_nodes'] = len(kg['nodes'])

 async def _detect_emergent_behaviors(self, experience: Dict):
 """Detect emergent behaviors from patterns."""
 # Simplified detection
 for pattern in experience.get('patterns', []):
 if pattern.get('confidence', 0) > 0.7 and pattern.get('novelty', 0) > 0.6:
 logger.info(f"Detected emergent behavior: {pattern['name']}")

 async def _update_models_from_experience(self, experience: Dict):
 """Update learning models from experience."""
 # Simplified model update
 pass

 def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
 """Calculate cosine similarity between embeddings."""
 try:
 v1 = np.array(embedding1)
 v2 = np.array(embedding2)
 dot_product = np.dot(v1, v2)
 norm1 = np.linalg.norm(v1)
 norm2 = np.linalg.norm(v2)
 
 if norm1 == 0 or norm2 == 0:
 return 0.0
 
 return float(dot_product / (norm1 * norm2))
 except Exception as e:
 logger.error(f"Failed to calculate similarity: {e}")
 return 0.0

 async def shutdown(self):
 """Shutdown service gracefully."""
 logger.info("Shutting down enhanced learning service...")
 self._running = False
