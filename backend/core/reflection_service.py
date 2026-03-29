import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from core.lancedb_service import LanceDBService
from core.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class Critique(Dict):
    """
    Represents a self-critique from M2.7.
    """
    id: str
    agent_id: str
    tenant_id: str
    intent: str
    action_taken: str
    outcome_state: str
    critique: str
    timestamp: str

class ReflectionService:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.lancedb = LanceDBService()
        self.embedding_service = EmbeddingService(tenant_id=tenant_id)

    async def add_critique(
        self, 
        agent_id: str, 
        intent: str, 
        action_taken: str, 
        outcome_state: str, 
        critique_text: str
    ) -> bool:
        """
        Add a new critique to the reflection pool.
        """
        table = self.lancedb.get_or_create_reflection_pool_table()
        if not table:
            logger.error("Reflection pool table not available")
            return False

        try:
            critique_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Create text for embedding
            embedding_text = f"Intent: {intent}\nAction: {action_taken}\nOutcome: {outcome_state}\nCritique: {critique_text}"
            vector = await self.embedding_service.generate_embedding(embedding_text)

            record = {
                "id": critique_id,
                "agent_id": agent_id,
                "tenant_id": self.tenant_id,
                "intent": intent,
                "action_taken": action_taken,
                "outcome_state": outcome_state,
                "critique": critique_text,
                "timestamp": timestamp,
                "vector": vector
            }

            table.add([record])
            logger.info(f"Added critique {critique_id} for agent {agent_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add critique: {e}")
            return False

    async def get_relevant_critiques(
        self, 
        agent_id: str, 
        current_intent: str, 
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant past critiques for the current intent.
        """
        table = self.lancedb.get_or_create_reflection_pool_table()
        if not table:
            return []

        try:
            # Embed the current intent to find similar past experiences
            query_vector = await self.embedding_service.generate_embedding(current_intent)
            
            # Search with agent_id and tenant_id filtering
            filter_str = f"agent_id == '{agent_id}' AND tenant_id == '{self.tenant_id}'"
            
            results = table.search(query_vector).where(filter_str).limit(limit).to_pandas()
            
            critiques = []
            for _, row in results.iterrows():
                critiques.append({
                    "intent": row["intent"],
                    "action_taken": row["action_taken"],
                    "outcome_state": row["outcome_state"],
                    "critique": row["critique"],
                    "timestamp": row["timestamp"]
                })
            
            return critiques
        except Exception as e:
            logger.warning(f"Failed to retrieve critiques: {e}")
            return []
