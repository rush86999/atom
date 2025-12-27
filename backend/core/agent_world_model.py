from typing import List, Dict, Any, Optional
import json
import logging
import uuid
from datetime import datetime
from pydantic import BaseModel

from core.models import AgentRegistry, AgentStatus
from core.lancedb_handler import LanceDBHandler, get_lancedb_handler

logger = logging.getLogger(__name__)

class AgentExperience(BaseModel):
    """
    Represents a unit of experience/learning for an agent.
    """
    id: str
    agent_id: str
    task_type: str        # e.g. "reconciliation", "outreach"
    input_summary: str    # "Reconcile SKU-123"
    outcome: str          # "Success", "Failure"
    learnings: str        # "Mismatch due to timing difference"
    artifacts: List[str] = []
    
    # Context for Scoping
    agent_role: str       # e.g. "Finance", "Operations"
    specialty: Optional[str] = None
    timestamp: datetime

class WorldModelService:
    def __init__(self, workspace_id: str = "default"):
        self.db = get_lancedb_handler(workspace_id)
        self.table_name = "agent_experience"
        self._ensure_table()

    def _ensure_table(self):
        """Ensure the experience table exists"""
        if self.db.db is None:
            return
            
        if self.table_name not in self.db.db.table_names():
            # We use the generic document schema but will enforce structure in metadata
            self.db.create_table(self.table_name)
            logger.info(f"Created agent_experience table: {self.table_name}")

    async def record_experience(self, experience: AgentExperience) -> bool:
        """
        Save an agent's experience to the World Model.
        """
        # Convert to text for embedding
        # We bury the "meaning" in the text field so vector search finds semantic matches
        text_representation = (
            f"Task: {experience.task_type}\n"
            f"Input: {experience.input_summary}\n"
            f"Outcome: {experience.outcome}\n"
            f"Learnings: {experience.learnings}"
        )
        
        metadata = {
            "agent_id": experience.agent_id,
            "task_type": experience.task_type,
            "outcome": experience.outcome,
            "agent_role": experience.agent_role,
            "specialty": experience.specialty,
            "artifacts": experience.artifacts,
            "type": "experience"
        }
        
        return self.db.add_document(
            table_name=self.table_name,
            text=text_representation,
            source=f"agent_{experience.agent_id}",
            metadata=metadata,
            user_id="agent_system", # System owned
            extract_knowledge=False # Don't re-ingest as generic knowledge
        )

    async def record_formula_usage(
        self,
        agent_id: str,
        agent_role: str,
        formula_id: str,
        formula_name: str,
        task_description: str,
        inputs: Dict[str, Any],
        result: Any,
        success: bool,
        learnings: str = ""
    ) -> bool:
        """
        Record a formula usage as part of agent learning.
        
        This allows agents to learn which formulas work best for specific tasks!
        Over time, successful formula applications improve recall ranking.
        
        Args:
            agent_id: The agent that used the formula
            agent_role: The agent's category (e.g., "Finance")
            formula_id: ID of the formula used
            formula_name: Human-readable formula name
            task_description: What task the agent was performing
            inputs: The input values used
            result: The calculated result
            success: Whether the calculation met expectations
            learnings: Optional notes about what was learned
        """
        text_representation = (
            f"Task: formula_application\n"
            f"Input: Applied '{formula_name}' for {task_description}\n"
            f"Outcome: {'Success' if success else 'Failure'}\n"
            f"Learnings: {learnings or f'Formula {formula_name} used with inputs {inputs}'}"
        )
        
        metadata = {
            "agent_id": agent_id,
            "task_type": "formula_application",
            "outcome": "Success" if success else "Failure",
            "agent_role": agent_role,
            "specialty": "formulas",
            "artifacts": [formula_id],
            "type": "experience",
            # Formula-specific metadata
            "formula_id": formula_id,
            "formula_name": formula_name,
            "formula_inputs": json.dumps(inputs) if inputs else "{}",
            "formula_result": str(result)
        }
        
        logger.info(f"Recording formula usage: {formula_name} by agent {agent_id} - {'Success' if success else 'Failure'}")
        
        return self.db.add_document(
            table_name=self.table_name,
            text=text_representation,
            source=f"agent_{agent_id}",
            metadata=metadata,
            user_id="agent_system",
            extract_knowledge=False
        )


    async def recall_experiences(
        self, 
        agent: AgentRegistry, 
        current_task_description: str,
        limit: int = 5
    ) -> Dict[str, List[Any]]:
        """
        Retrieve relevant past experiences AND general knowledge.
        
        Returns:
            {
                "experiences": List[AgentExperience], # Scoped to role
                "knowledge": List[Dict] # General knowledge (unscoped or broad scope)
            }
        """
        # 1. Search semantic matches for the current task in Experience Table
        exp_results = self.db.search(
            table_name=self.table_name,
            query=current_task_description,
            limit=limit * 3 
        )
        
        valid_experiences = []
        agent_category = agent.category.lower() if agent.category else "general"
        
        for res in exp_results:
            meta = res.get("metadata", {})
            memory_role = meta.get("agent_role", "").lower()
            creator_id = meta.get("agent_id")
            
            # Scoped Access Logic for Experiences
            is_creator = (creator_id == agent.id)
            is_role_match = (memory_role == agent_category)
            
            if is_creator or is_role_match:
                valid_experiences.append(AgentExperience(
                    id=res["id"],
                    agent_id=creator_id or "unknown",
                    task_type=meta.get("task_type", "unknown"),
                    input_summary=res["text"].split("\n")[1].replace("Input: ", "") if "Input: " in res["text"] else "",
                    outcome=meta.get("outcome", "unknown"),
                    learnings=res["text"].split("Learnings: ")[-1] if "Learnings: " in res["text"] else "",
                    artifacts=meta.get("artifacts", []),
                    agent_role=meta.get("agent_role", ""),
                    specialty=meta.get("specialty"),
                    timestamp=datetime.fromisoformat(res["created_at"])
                ))
            if len(valid_experiences) >= limit:
                break
        
        # 2. Search General Knowledge (Documents & Knowledge Graph)
        # This is "Atom's memory" created from ingestion
        knowledge_results = self.db.search(
            table_name="documents", # Assuming generic docs are here
            query=current_task_description,
            limit=limit,
            user_id=None # No user filter for general knowledge (or use system user)
        )
        
        # Also query Knowledge Graph if relationships are relevant
        graph_context = ""
        try:
            from core.graphrag_engine import graphrag_engine
            graph_context = graphrag_engine.get_context_for_ai(self.db.workspace_id, current_task_description)
        except Exception as ge:
            logger.warning(f"GraphRAG recall failed: {ge}")

        # 3. Search Formulas (Phase 30: Intelligent Formula Storage)
        # Include relevant formulas from Atom's formula memory
        formula_results = []
        try:
            from core.formula_memory import get_formula_manager
            formula_manager = get_formula_manager(self.db.workspace_id if hasattr(self.db, 'workspace_id') else "default")
            
            # Search for formulas relevant to the current task
            formulas = formula_manager.search_formulas(
                query=current_task_description,
                domain=agent_category if agent_category != "general" else None,
                limit=limit
            )
            
            formula_results = [
                {
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "expression": f.get("expression"),
                    "domain": f.get("domain"),
                    "use_case": f.get("use_case"),
                    "parameters": f.get("parameters", []),
                    "type": "formula"
                }
                for f in formulas
            ]
            
            logger.info(f"Found {len(formula_results)} relevant formulas for agent task")
        except Exception as fe:
            logger.warning(f"Formula recall failed: {fe}")

        return {
            "experiences": valid_experiences,
            "knowledge": knowledge_results,
            "knowledge_graph": graph_context, # Phase 31: Include KG context
            "formulas": formula_results  # Phase 30: Include formulas in agent memory
        }

