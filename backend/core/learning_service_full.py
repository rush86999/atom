"""
Comprehensive Learning Service - Full Learning & Adaptation Engine

This service provides complete learning and adaptation capabilities for agents:
- Experience recording and analysis
- Model training and updates
- Adaptation strategy generation
- Knowledge graph management
- Emergent behavior detection
- Reflection synthesis
- Pattern recognition

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
from core.database import get_db

logger = logging.getLogger(__name__)

class ExperienceType(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    CORRECTION = "correction"
    FEEDBACK = "feedback"
    INTERACTION = "interaction"
    OBSERVATION = "observation"

class AdaptationType(str, Enum):
    REACTIVE = "reactive"
    INCREMENTAL = "incremental"
    TRANSFORMATIVE = "transformative"
    EVOLUTIONARY = "evolutionary"

class NodeType(str, Enum):
    CONCEPT = "concept"
    ENTITY = "entity"
    RELATION = "relation"
    RULE = "rule"
    PATTERN = "pattern"
    STRATEGY = "strategy"

@dataclass
class LearningExperience:
    """Complete learning experience record"""
    id: str
    type: str

    agent_id: str
    task_description: str
    inputs: Dict[str, Any]
    actions: List[Dict[str, Any]]
    outcomes: Dict[str, float]
    feedback: Dict[str, Any]
    reflections: List[Dict[str, Any]]
    patterns: List[Dict[str, Any]]
    vector: List[float]
    context: Dict[str, Any]
    timestamp: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class LearningModel:
    """Learning model with performance metrics"""
    id: str

    model_type: str
    name: str
    description: str
    algorithm: str
    parameters: Dict[str, Any]
    performance: Dict[str, float]
    data: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

@dataclass
class AdaptationStrategy:
    """Adaptation strategy for agent improvement"""
    id: str

    type: str
    name: str
    description: str
    trigger: Dict[str, Any]
    mechanism: Dict[str, Any]
    scope: Dict[str, Any]
    impact: Dict[str, float]
    validation: Dict[str, Any]
    status: str
    applied_at: Optional[datetime]
    results: Optional[Dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

@dataclass
class KnowledgeNode:
    """Knowledge graph node"""
    id: str

    type: str
    label: str
    properties: Dict[str, Any]
    embeddings: List[float]
    confidence: float
    frequency: int
    last_accessed: datetime
    importance: float

@dataclass
class KnowledgeEdge:
    """Knowledge graph edge"""
    id: str

    source: str
    target: str
    type: str
    weight: float
    properties: Dict[str, Any]
    confidence: float
    direction: str

@dataclass
class EmergentBehavior:
    """Emergent behavior pattern"""
    id: str

    name: str
    description: str
    behavior_type: str
    trigger_conditions: Dict[str, Any]
    pattern_sequence: List[Dict[str, Any]]
    characteristics: Dict[str, float]
    outcomes: Dict[str, float]
    evidence: Dict[str, Any]
    status: str
    discovered_at: datetime
    last_observed: datetime

class LearningService:
    """
    Comprehensive learning and adaptation service.

    Implements full cognitive learning architecture:
    - Experience-based learning
    - Model training and adaptation
    - Knowledge graph construction
    - Pattern recognition
    - Strategy generation
    """

    def __init__(self, db: Session, llm_service: Optional[LLMService] = None, embedding_service: Optional[EmbeddingService] = None):
        self.db = db
        self.llm_service = llm_service or LLMService(workspace_id="system")
        self.embedding_service = embedding_service or EmbeddingService()

        # In-memory caches for hot path
        self.models_cache: Dict[str, LearningModel] = {}
        self.experiences_cache: Dict[str, LearningExperience] = {}
        self.strategies_cache: Dict[str, AdaptationStrategy] = {}
        self.knowledge_graphs: Dict[str, Dict[str, Any]] = {} # tenant_id (multi-tenant only, removed for upstream) (removed for upstream) -> graph

        # Background task flags
        self._running = True

        # ============================================================================
        # EXPERIENCE RECORDING
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
        """
        Record a complete learning experience.

        This is the main entry point for agent learning. It:
        1. Creates experience record
        2. Generates embedding vector
        3. Extracts patterns and reflections
        4. Triggers model updates
        """
        experience_id = f"exp_{uuid.uuid4().hex}"
        timestamp = datetime.now(timezone.utc)

        try:
            # Generate embedding for semantic search
            vector = await self._generate_experience_embedding(task_description, actions, outcomes)

            # Create experience record
            experience = LearningExperience(
            id=experience_id,
            type=experience_type,
            agent_id=agent_id,
            task_description=task_description,
            inputs=inputs,
            actions=actions,
            outcomes=outcomes,
            feedback=feedback or {},
            reflections=[],
            patterns=[],
            vector=vector,
            context=context or {},
            timestamp=timestamp
            )

            # Store in cache
            self.experiences_cache[experience_id] = experience

            # Persist to database
            await self._persist_experience(experience)

            # Extract patterns and reflections asynchronously
            asyncio.create_task(self._process_experience(experience_id))

            logger.info(f"Recorded experience {experience_id} for agent {agent_id}")
            return experience_id

        except Exception as e:
            logger.error(f"Failed to record experience: {e}")
            raise

    async def _process_experience(self, experience_id: str):
        """Process experience to extract learnings"""
        try:
            experience = self.experiences_cache.get(experience_id)
            if not experience:
                logger.warning(f"Experience {experience_id} not found in cache")
                return

                # Extract patterns
                patterns = await self._identify_patterns(experience)
                experience.patterns = patterns

                # Generate reflections
                reflections = await self._generate_reflections(experience)
                experience.reflections = reflections

                # Update knowledge graph
                await self._update_knowledge_graph(experience)

                # Detect emergent behaviors
                await self._detect_emergent_behaviors(experience)

                # Trigger model updates
                await self._update_models_from_experience(experience)

                logger.info(f"Processed experience {experience_id}")

        except Exception as e:
            logger.error(f"Failed to process experience {experience_id}: {e}")

    async def _generate_experience_embedding(
    self,
    task_description: str,
    actions: List[Dict[str, Any]],
    outcomes: Dict[str, float]
    ) -> List[float]:
        """Generate embedding vector for experience"""
        try:
            # Create text representation
            text = f"{task_description} " + " ".join([
            f"{a.get('type', '')} {json.dumps(a.get('parameters', {}))}"
            for a in actions
            ])

            # Generate embedding using backend service
            embedding = await self.embedding_service.generate_embedding(text)
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return [0.0] * 1536 # Fallback to zero vector

    async def _persist_experience(self, experience: LearningExperience):
        """Persist experience to database"""
        try:
            from core.models import AgentLearning, CognitiveExperience

            # Use CognitiveExperience model if available
            experience_record = CognitiveExperience(
            id=experience.id,
            agent_id=experience.agent_id,
            experience_type=experience.type,
            task_type=experience.task_description,
            input_summary=json.dumps(experience.inputs),
            output_summary=json.dumps(experience.actions),
            outcome=json.dumps(experience.outcomes),
            learnings={
            "patterns": experience.patterns,
            "reflections": experience.reflections,
            "vector": experience.vector
            },
            effectiveness_score=experience.outcomes.get('primary', 0.5) if experience.outcomes else 0.5
            )

            self.db.add(experience_record)
            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to persist experience: {e}")
            self.db.rollback()
            raise

            # ============================================================================
            # PATTERN RECOGNITION
            # ============================================================================

    async def _identify_patterns(self, experience: LearningExperience) -> List[Dict[str, Any]]:
        """Identify patterns in experience"""
        patterns = []

        try:
            # Analyze action sequences
            if len(experience.actions) > 1:
                sequence_pattern = await self._extract_action_sequence_pattern(experience.actions)
                if sequence_pattern:
                    patterns.append(sequence_pattern)

                    # Analyze outcome patterns
                    outcome_pattern = self._extract_outcome_pattern(experience.outcomes)
                    if outcome_pattern:
                        patterns.append(outcome_pattern)

                        # Analyze parameter impact
                        param_patterns = await self._analyze_parameter_impact(experience)
                        patterns.extend(param_patterns)

        except Exception as e:
            logger.error(f"Failed to identify patterns: {e}")

            return patterns

    async def _extract_action_sequence_pattern(self, actions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Extract patterns from action sequences"""
        try:
            # Use LLM to analyze sequence
            sequence_text = " -> ".join([a.get('type', 'unknown') for a in actions])

            prompt = f"""Analyze this action sequence and identify the pattern:
            {sequence_text}

            Return a JSON object with:
            - pattern_name: Name of the pattern
            - description: Brief description
            - effectiveness: Rating 0-1
            - generalizability: How widely applicable (0-1)
            """

            result = await self.llm_service.generate_text(
            prompt=prompt,
            system_prompt="You are a pattern recognition expert. Analyze action sequences and identify reusable patterns."
            )

            # Parse result (simplified - in production use structured output)
            return {
            "type": "action_sequence",
            "name": "Action Sequence Pattern",
            "description": sequence_text,
            "confidence": 0.7,
            "novelty": 0.3
            }

        except Exception as e:
            logger.error(f"Failed to extract sequence pattern: {e}")
            return None

    def _extract_outcome_pattern(self, outcomes: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Extract patterns from outcomes"""
        try:
            primary = outcomes.get('primary', 0.5)

            if primary > 0.8:
                return {
                "type": "success",
                "name": "High Success Pattern",
                "confidence": primary,
                "novelty": 0.2
                }
            elif primary < 0.3:
                return {
                "type": "failure",
                "name": "Failure Pattern",
                "confidence": 1 - primary,
                "novelty": 0.5
                }

        except Exception as e:
            logger.error(f"Failed to extract outcome pattern: {e}")

            return None

    async def _analyze_parameter_impact(self, experience: LearningExperience) -> List[Dict[str, Any]]:
        """Analyze how parameters affected outcomes"""
        patterns = []

        try:
            # Extract parameters from actions
            parameters = {}
            for action in experience.actions:
                params = action.get('parameters', {})
                parameters.update(params)

                if not parameters:
                    return patterns

                    # Analyze correlation with outcomes
                    for param_name, param_value in parameters.items():
                        patterns.append({
                        "type": "parameter_impact",
                        "name": f"Parameter {param_name}",
                        "value": str(param_value),
                        "impact": experience.outcomes.get('primary', 0.5),
                        "confidence": 0.6
                        })

        except Exception as e:
            logger.error(f"Failed to analyze parameter impact: {e}")

            return patterns

            # ============================================================================
            # REFLECTION SYNTHESIS
            # ============================================================================

    async def _generate_reflections(self, experience: LearningExperience) -> List[Dict[str, Any]]:
        """Generate reflections from experience"""
        reflections = []

        try:
            # Focus on negative experiences for learning
            if experience.type == 'failure' or experience.outcomes.get('primary', 0.5) < 0.5:
                reflection = await self._synthesize_failure_reflection(experience)
                if reflection:
                    reflections.append(reflection)

                    # Generate improvement suggestions
                    improvement = await self._generate_improvement_suggestion(experience)
                    if improvement:
                        reflections.append(improvement)

        except Exception as e:
            logger.error(f"Failed to generate reflections: {e}")

            return reflections

    async def _synthesize_failure_reflection(self, experience: LearningExperience) -> Optional[Dict[str, Any]]:
        """Synthesize learning from failure"""
        try:
            # Prepare context for LLM
            context = {
            "task": experience.task_description,
            "actions": experience.actions,
            "outcomes": experience.outcomes,
            "feedback": experience.feedback
            }

            prompt = f"""Analyze this failed agent execution and extract a key learning:
            {json.dumps(context, indent=2)}

            Provide a "rule of thumb" in this format:
            "When [condition], avoid [action] because [reason]."

            Return only the rule, no explanation.
            """

            result = await self.llm_service.generate_text(
            prompt=prompt,
            system_prompt="You are an AI optimization expert. Analyze failures and extract actionable rules."
            )

            return {
            "insight": result.get('content', ''),
            "impact": "high",
            "generalizability": 0.7,
            "novelty": 0.3
            }

        except Exception as e:
            logger.error(f"Failed to synthesize failure reflection: {e}")
            return None

    async def _generate_improvement_suggestion(self, experience: LearningExperience) -> Optional[Dict[str, Any]]:
        """Generate improvement suggestion"""
        try:
            prompt = f"""Given this agent execution:
            Task: {experience.task_description}
            Outcome: {json.dumps(experience.outcomes)}

            Suggest one specific improvement for future executions.
            Be concise and actionable.
            """

            result = await self.llm_service.generate_text(prompt=prompt)

            return {
            "insight": f"Improvement: {result.get('content', '')}",
            "impact": "medium",
            "generalizability": 0.5,
            "novelty": 0.2
            }

        except Exception as e:
            logger.error(f"Failed to generate improvement: {e}")
            return None

            # ============================================================================
            # ADAPTATION STRATEGIES
            # ============================================================================

    async def generate_adaptations(
    self,
    
    agent_id: Optional[str] = None,
    limit: int = 50
    ) -> List[AdaptationStrategy]:
        """Generate adaptation strategies based on recent experiences"""

        try:
            # Get recent experiences
            experiences = await self._get_recent_experiences("default", agent_id, limit)

            if len(experiences) < 5:
                logger.info("Not enough experiences to generate adaptations")
                return []

                adaptations = []

                # Analyze success patterns
                successful = [e for e in experiences if e.outcomes.get('primary', 0.5) > 0.7]
                failed = [e for e in experiences if e.outcomes.get('primary', 0.5) <= 0.5]

                # Pattern 1: High failure rate on specific actions
                action_failures = self._analyze_action_failures(failed)
                for action_type, data in action_failures.items():
                    if data['count'] >= 3:
                        strategy = await self._create_failure_reduction_strategy(
                        )
                        if strategy:
                            adaptations.append(strategy)

                            # Pattern 2: High success rate - suggest autonomy increase
                            if len(successful) >= 10:
                                success_rate = len(successful) / len(experiences)
                                if success_rate > 0.9:
                                    strategy = await self._create_autonomy_increase_strategy(
                                    )
                                    if strategy:
                                        adaptations.append(strategy)

                                        # Pattern 3: Quality improvements
                                        avg_quality = sum(e.outcomes.get('quality', 0.5) for e in experiences) / len(experiences)
                                        if avg_quality < 0.6:
                                            strategy = await self._create_quality_improvement_strategy(
                                            )
                                            if strategy:
                                                adaptations.append(strategy)

                                                logger.info(f"Generated {len(adaptations)} adaptation strategies")
                                                return adaptations

        except Exception as e:
            logger.error(f"Failed to generate adaptations: {e}")
            return []

    def _analyze_action_failures(self, failed_experiences: List[LearningExperience]) -> Dict[str, Dict]:
        """Analyze which actions fail most often"""
        failures = {}

        for exp in failed_experiences:
            for action in exp.actions:
                action_type = action.get('type', 'unknown')
                if action_type not in failures:
                    failures[action_type] = {'count': 0, 'examples': []}
                    failures[action_type]['count'] += 1
                    failures[action_type]['examples'].append(exp.id)

                    return failures

    async def _create_failure_reduction_strategy(
    self,
    
    action_type: str,
    failure_data: Dict
    ) -> Optional[AdaptationStrategy]:
        """Create strategy to reduce failures for specific action type"""
        try:
            strategy_id = f"strat_{uuid.uuid4().hex}"

            strategy = AdaptationStrategy(
            id=strategy_id,
            type="reactive",
            name=f"Reduce {action_type} failures",
            description=f"Agent is failing at {action_type} (failed {failure_data['count']} times recently)",
            trigger={
            "conditions": {"action_type": action_type},
            "thresholds": {"failure_rate": 0.5},
            "frequency": 24
            },
            mechanism={
            "algorithm": "restriction",
            "parameters": {
            "action_type": action_type,
            "requires_approval": True
            },
            "constraints": {}
            },
            scope={
            "components": [action_type],
            "domains": ["execution"],
            "depth": 0
            },
            impact={
            "expected": {
            "performance": 0.2,
            "efficiency": 0,
            "quality": 0.1,
            "learning": 0.1
            }
            },
            validation={
            "methodology": "failure_rate_threshold",
            "metrics": ["failure_rate", "action_count"],
            "significance": 0.95,
            "duration": 24
            },
            status="testing",
            applied_at=None,
            results=None,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
            )

            # Cache and persist
            self.strategies_cache[strategy_id] = strategy
            await self._persist_strategy(strategy)

            return strategy

        except Exception as e:
            logger.error(f"Failed to create failure reduction strategy: {e}")
            return None

    async def _create_autonomy_increase_strategy(
    self,
    
    agent_id: Optional[str],
    success_rate: float
    ) -> Optional[AdaptationStrategy]:
        """Create strategy to increase agent autonomy"""
        try:
            strategy_id = f"strat_{uuid.uuid4().hex}"

            strategy = AdaptationStrategy(
            id=strategy_id,
            type="incremental",
            name=f"Increase autonomy for agent {agent_id or 'all'}",
            description=f"Agent has {success_rate*100:.0f}% success rate",
            trigger={
            "conditions": {"success_rate": str(success_rate)},
            "thresholds": {"success_rate": 0.9},
            "frequency": 24
            },
            mechanism={
            "algorithm": "autonomy_increase",
            "parameters": {
            "maturity_level": "increment",
            "value": 1
            },
            "constraints": {}
            },
            scope={
            "components": ["autonomy"],
            "domains": ["governance"],
            "depth": 1
            },
            impact={
            "expected": {
            "performance": 0.1,
            "efficiency": 0.2,
            "quality": 0,
            "learning": 0.1
            }
            },
            validation={
            "methodology": "success_rate_threshold",
            "metrics": ["success_rate", "experience_count"],
            "significance": 0.9,
            "duration": 24
            },
            status="testing",
            applied_at=None,
            results=None,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
            )

            self.strategies_cache[strategy_id] = strategy
            await self._persist_strategy(strategy)

            return strategy

        except Exception as e:
            logger.error(f"Failed to create autonomy strategy: {e}")
            return None

    async def _create_quality_improvement_strategy(
    self,
    
    avg_quality: float
    ) -> Optional[AdaptationStrategy]:
        """Create strategy to improve response quality"""
        try:
            strategy_id = f"strat_{uuid.uuid4().hex}"

            strategy = AdaptationStrategy(
            id=strategy_id,
            type="transformative",
            name="Improve response quality",
            description=f"Average quality score is {avg_quality:.2f}, below threshold",
            trigger={
            "conditions": {"quality_threshold": "0.6", "current_quality": str(avg_quality)},
            "thresholds": {"quality": 0.6},
            "frequency": 12
            },
            mechanism={
            "algorithm": "parameter_tuning",
            "parameters": {
            "temperature": "decrease",
            "value": 0.1
            },
            "constraints": {}
            },
            scope={
            "components": ["llm_parameters"],
            "domains": ["generation"],
            "depth": 0
            },
            impact={
            "expected": {
            "performance": 0,
            "efficiency": 0,
            "quality": 0.2,
            "learning": 0
            }
            },
            validation={
            "methodology": "quality_score_threshold",
            "metrics": ["quality_score"],
            "significance": 0.9,
            "duration": 12
            },
            status="testing",
            applied_at=None,
            results=None,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
            )

            self.strategies_cache[strategy_id] = strategy
            await self._persist_strategy(strategy)

            return strategy

        except Exception as e:
            logger.error(f"Failed to create quality strategy: {e}")
            return None

    async def _persist_strategy(self, strategy: AdaptationStrategy):
        """Persist strategy to database"""
        try:
            from core.models import AgentLearning

            # Store as learning model with strategy type
            strategy_record = AgentLearning(
            agent_id=strategy.mechanism['parameters'].get('action_type', 'strategy'),
            learning_type='adaptation_strategy',
            parameters_json=asdict(strategy),
            last_updated_at=strategy.updated_at
            )

            self.db.add(strategy_record)
            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to persist strategy: {e}")
            self.db.rollback()

            # ============================================================================
            # KNOWLEDGE GRAPH
            # ============================================================================

    async def get_knowledge_graph(self) -> Dict[str, Any]:
        """Get knowledge graph for tenant"""
        if True:  # tenant_id check removed for upstream
            self.knowledge_graphs["default"] = {
            'nodes': {},
            'edges': {},
            'clusters': {},
            'metrics': {
            'total_nodes': 0,
            'total_edges': 0,
            'density': 0,
            'clustering_coefficient': 0
            }
            }

            return self.knowledge_graphs["default"]

    async def search_knowledge(
    self,
    
    query: str,
    limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search knowledge graph by query"""
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query)

            kg = await self.get_knowledge_graph("default")
            results = []

            # Search nodes by similarity
            for node_id, node_data in kg['nodes'].items():
                if 'embeddings' in node_data:
                    similarity = self._calculate_similarity(
                    query_embedding,
                    node_data['embeddings']
                    )

                    if similarity > 0.5:
                        results.append({
                        'node': node_data,
                        'score': similarity,
                        'explanation': f"Match found for query: {query}"
                        })

                        # Sort by score and return top results.sort(key=lambda x: x['score'], reverse=True)
                        return results[:limit]

        except Exception as e:
            logger.error(f"Failed to search knowledge: {e}")
            return []

    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between embeddings"""
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

    async def _update_knowledge_graph(self, experience: LearningExperience):
        """Update knowledge graph with new experience"""
        try:
            kg = await self.get_knowledge_graph("default")

            # Extract entities from experience
            entities = await self._extract_entities(experience)

            # Add nodes for entities
            for entity in entities:
                node_id = f"entity_{entity.get('name', uuid.uuid4().hex)}"

                if node_id not in kg['nodes']:
                    # Generate embedding for entity
                    embedding = await self.embedding_service.generate_embedding(
                    entity.get('name', '')
                    )

                    kg['nodes'][node_id] = {
                    'id': node_id,

                    'type': entity.get('type', 'concept'),
                    'label': entity.get('name', 'Unknown'),
                    'properties': entity,
                    'embeddings': embedding,
                    'confidence': 0.8,
                    'frequency': 1,
                    'last_accessed': datetime.now(timezone.utc),
                    'importance': 0.5
                    }
                else:
                    # Update existing node
                    kg['nodes'][node_id]['frequency'] += 1
                    kg['nodes'][node_id]['last_accessed'] = datetime.now(timezone.utc)

                    # Update metrics
                    kg['metrics']['total_nodes'] = len(kg['nodes'])
                    kg['metrics']['total_edges'] = len(kg['edges'])

        except Exception as e:
            logger.error(f"Failed to update knowledge graph: {e}")

    async def _extract_entities(self, experience: LearningExperience) -> List[Dict[str, Any]]:
        """Extract entities from experience"""
        entities = []

        try:
            # Use LLM to extract entities
            prompt = f"""Extract key entities from this agent experience:
            Task: {experience.task_description}
            Actions: {json.dumps(experience.actions[:3])} # First 3 actions

            Return a JSON list of entities with:
            - name: Entity name
            - type: One of 'concept', 'entity', 'action', 'outcome'
            - description: Brief description
            """

            result = await self.llm_service.generate_text(prompt=prompt)

            # Parse result (simplified)
            # In production, use structured output parsing
            entities.append({
            'name': experience.task_description[:50],
            'type': 'concept',
            'description': experience.task_description
            })

        except Exception as e:
            logger.error(f"Failed to extract entities: {e}")

            return entities

            # ============================================================================
            # EMERGENT BEHAVIOR DETECTION
            # ============================================================================

    async def _detect_emergent_behaviors(self, experience: LearningExperience):
        """Detect emergent behaviors from experience patterns"""
        try:
            for pattern in experience.patterns:
                if pattern.get('confidence', 0) > 0.7 and pattern.get('novelty', 0) > 0.6:
                    behavior = await self._create_emergent_behavior(
                    "default",
                    pattern
                    )
                    if behavior:
                        logger.info(f"Detected emergent behavior: {behavior.id}")

        except Exception as e:
            logger.error(f"Failed to detect emergent behaviors: {e}")

    async def _create_emergent_behavior(
    self,
    
    pattern: Dict[str, Any]
    ) -> Optional[EmergentBehavior]:
        """Create emergent behavior record"""
        try:
            behavior_id = f"beh_{uuid.uuid4().hex}"
            now = datetime.now(timezone.utc)

            behavior = EmergentBehavior(
            id=behavior_id,
            name=pattern.get('name', 'Unknown Pattern'),
            description=f"Emergent behavior detected from pattern: {pattern.get('name', '')}",
            behavior_type=self._classify_behavior_type(pattern),
            trigger_conditions=pattern.get('trigger', {}),
            pattern_sequence=[{
            'action': pattern.get('name', ''),
            'parameters': pattern,
            'timing': 0
            }],
            characteristics={
            'complexity': pattern.get('confidence', 0.5),
            'novelty': pattern.get('novelty', 0.5),
            'utility': 0.5,
            'persistence': 0.5,
            'scalability': 0.5
            },
            outcomes={
            'success_rate': 0.5,
            'efficiency': 0.5,
            'learning_value': 0.7,
            'adaptability': 0.5
            },
            evidence={
            'occurrences': 1,
            'confidence': pattern.get('confidence', 0.5),
            'generality': 0.5,
            'robustness': 0.5
            },
            status='emerging',
            discovered_at=now,
            last_observed=now
            )

            return behavior

        except Exception as e:
            logger.error(f"Failed to create emergent behavior: {e}")
            return None

    def _classify_behavior_type(self, pattern: Dict[str, Any]) -> str:
        """Classify behavior type from pattern"""
        # Simplified classification
        confidence = pattern.get('confidence', 0.5)
        novelty = pattern.get('novelty', 0.5)

        if confidence > 0.8 and novelty < 0.3:
            return 'stable'
        elif confidence > 0.6 and novelty > 0.6:
            return 'adaptive'
        elif novelty > 0.8:
            return 'creative'
        else:
            return 'emerging'

            # ============================================================================
            # MODEL UPDATES
            # ============================================================================

    async def _update_models_from_experience(self, experience: LearningExperience):
        """Update learning models based on experience"""
        try:
            # Get recent experiences for context
            recent_experiences = await self._get_recent_experiences(
            "default",
            experience.agent_id,
            limit=50
            )

            if not recent_experiences:
                return

                # Calculate success rate
                success_count = sum(
                1 for e in recent_experiences
                if e.type == 'success' or e.outcomes.get('primary', 0.5) > 0.8
                )
                total_count = len(recent_experiences)
                success_rate = success_count / total_count if total_count > 0 else 0

                # Update models
                for model_id, model in list(self.models_cache.items()):
                    if True:
                        # Adjust confidence based on success rate
                        if success_rate > 0.8:
                            model.performance['confidence'] = min(1.0, model.performance['confidence'] + 0.01)
                        elif success_rate < 0.5:
                            model.performance['confidence'] = max(0.1, model.performance['confidence'] - 0.02)

                            model.performance['accuracy'] = (
                            model.performance['accuracy'] * 0.9 + success_rate * 0.1
                            )
                            model.updated_at = datetime.now(timezone.utc)

                            # Persist update
                            await self._persist_model(model)

                            logger.info(f"Updated models based on {total_count} experiences (success rate: {success_rate:.2f})")

        except Exception as e:
            logger.error(f"Failed to update models: {e}")

    async def _get_recent_experiences(
    self,
    
    agent_id: Optional[str] = None,
    limit: int = 50
    ) -> List[LearningExperience]:
        """Get recent experiences from cache/database"""
        try:
            # Filter from cache
            experiences = [
            exp for exp in self.experiences_cache.values()
            if exp
            ]

            if agent_id:
                experiences = [exp for exp in experiences if exp.agent_id == agent_id]

                # Sort by timestamp and return top N
                experiences.sort(key=lambda x: x.timestamp, reverse=True)
                return experiences[:limit]

        except Exception as e:
            logger.error(f"Failed to get recent experiences: {e}")
            return []

    async def _persist_model(self, model: LearningModel):
        """Persist model to database"""
        try:
            from core.models import AgentLearning

            model_record = AgentLearning(
            agent_id=model.id,
            learning_type='model',
            parameters_json=asdict(model),
            last_updated_at=model.updated_at
            )

            self.db.add(model_record)
            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to persist model: {e}")
            self.db.rollback()

            # ============================================================================
            # LEARNING STATE & MONITORING
            # ============================================================================

    async def get_learning_state(self) -> Dict[str, Any]:
        """Get comprehensive learning state for tenant"""
        try:
            # Get models
            models = [m for m in self.models_cache.values() if m]
            avg_accuracy = (
            sum(m.performance['accuracy'] for m in models) / len(models)
            if models else 0.5
            )

            # Get experiences
            experiences = [e for e in self.experiences_cache.values() if e]
            today = datetime.now(timezone.utc) - timedelta(days=1)
            today_experiences = [e for e in experiences if e.timestamp > today]

            # Get strategies
            strategies = [s for s in self.strategies_cache.values() if s]
            active_strategies = [s for s in strategies if s.status == 'active']

            # Get knowledge graph stats
            kg = await self.get_knowledge_graph("default")

            return {
            'models': {
            'total': len(models),
            'average_accuracy': avg_accuracy
            },
            'experiences': {
            'total': len(experiences),
            'today': len(today_experiences)
            },
            'adaptations': {
            'total': len(strategies),
            'active': len(active_strategies)
            },
            'knowledge_graph': {
            'nodes': kg['metrics']['total_nodes'],
            'edges': kg['metrics']['total_edges'],
            'density': kg['metrics']['density']
            },
            'learning_velocity': self._calculate_learning_velocity(experiences),
            'adaptation_rate': len(active_strategies) / max(len(experiences), 1)
            }

        except Exception as e:
            logger.error(f"Failed to get learning state: {e}")
            return {}

    def _calculate_learning_velocity(self, experiences: List[LearningExperience]) -> float:
        """Calculate learning velocity from experiences"""
        if not experiences:
            return 0.0

            # Calculate rate of improvement
            recent = experiences[:10]
            if len(recent) < 2:
                return 0.5

                avg_recent = sum(e.outcomes.get('primary', 0.5) for e in recent) / len(recent)
                older = experiences[10:20] if len(experiences) > 10 else recent
                avg_older = sum(e.outcomes.get('primary', 0.5) for e in older) / len(older)

                return avg_recent - avg_older

                # ============================================================================
                # CLEANUP
                # ============================================================================

    async def shutdown(self):
        """Shutdown learning service gracefully"""
        logger.info("Shutting down learning service...")
        self._running = False

        # Persist all cached data
        try:
            for model in self.models_cache.values():
                await self._persist_model(model)

                for strategy in self.strategies_cache.values():
                    await self._persist_strategy(strategy)

                    logger.info("Learning service shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
