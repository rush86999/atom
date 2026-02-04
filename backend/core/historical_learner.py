import json
import logging
from typing import Any, Dict, List

from core.business_intelligence import BusinessEventIntelligence
from core.knowledge_extractor import KnowledgeExtractor
from core.lancedb_handler import get_lancedb_handler

logger = logging.getLogger(__name__)

class HistoricalLifecycleLearner:
    """
    Scans historical communications to populate the business lifecycle.
    """

    def __init__(self, ai_service: Any = None, db_session: Any = None):
        self.lancedb = get_lancedb_handler()
        self.extractor = KnowledgeExtractor(ai_service)
        self.biz_intel = BusinessEventIntelligence(db_session)

    async def learn_from_history(self, workspace_id: str, user_id: str):
        """
        Retrieves all historical communications for a user and extracts business events.
        """
        logger.info(f"Starting historical lifecycle learning for user {user_id}")
        
        # 1. Fetch historical communications from LanceDB
        # We search with an empty filter to get everything for this user in communications
        # In a real system, we'd use pagination. For the prototype, we take the last 100.
        docs = self.lancedb.search(
            table_name="atom_communications",
            query="business correspondence", # Semantic hint to focus on biz stuff
            user_id=user_id,
            limit=100
        )
        
        if not docs:
            logger.info("No historical communications found to learn from.")
            return
        
        logger.info(f"Found {len(docs)} historical documents. Processing...")
        
        for doc in docs:
            content = doc.get("text", "")
            # 2. Extract knowledge from historical content
            knowledge = await self.extractor.extract_knowledge(content, source="historical_comm")
            
            # 3. Process the events to update system state (e.g., link POs to deals)
            if knowledge.get("entities") or knowledge.get("relationships"):
                await self.biz_intel.process_extracted_events(knowledge, workspace_id)
        
        logger.info(f"Historical learning complete for user {user_id}")
