import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from core.database import get_db_session
from core.lancedb_handler import LanceDBHandler, get_lancedb_handler
from core.models import AgentRegistry, AgentStatus, ChatMessage

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
    confidence_score: float = 0.5 # 0.0 to 1.0 (How confident are we this was a good run?)
    feedback_score: Optional[float] = None # -1.0 to 1.0 (Human feedback)
    artifacts: List[str] = []

    # TRACE Framework Metrics (Phase 6.6)
    step_efficiency: float = 1.0  # (Steps Taken / Expected Steps) - lower is better
    metadata_trace: Dict[str, Any] = {} # Detailed execution trace, plan adherence, etc.

    # Enhanced Rating Fields (NEW)
    thumbs_up_down: Optional[bool] = None  # Quick thumbs up/down feedback
    rating: Optional[int] = None  # Star rating (1-5)
    agent_execution_id: Optional[str] = None  # Link to agent execution
    feedback_type: Optional[str] = None  # Type of feedback (correction, rating, approval, comment)

    # Context for Scoping
    agent_role: str       # e.g. "Finance", "Operations"
    specialty: Optional[str] = None
    timestamp: datetime

class BusinessFact(BaseModel):
    """
    Represents a verified piece of business knowledge with citations.
    Distinct from experiential learning. Use for "Trusted Memory".
    """
    id: str
    fact: str             # "Invoices > $500 need VP approval"
    citations: List[str]  # ["policy.pdf:p4", "src/approvals.ts:L20"]
    reason: str           # Context/Why this is important
    source_agent_id: str
    created_at: datetime
    last_verified: datetime
    verification_status: str = "unverified" # unverified, verified, outdated
    metadata: Dict[str, Any] = {}

class WorldModelService:
    def __init__(self, workspace_id: str = "default"):
        self.db = get_lancedb_handler(workspace_id)
        self.table_name = "agent_experience"
        self.facts_table_name = "business_facts"
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure the experience and facts tables exist"""
        if self.db.db is None:
            return
            
        if self.table_name not in self.db.db.table_names():
            # We use the generic document schema but will enforce structure in metadata
            self.db.create_table(self.table_name)
            logger.info(f"Created agent_experience table: {self.table_name}")

        if self.facts_table_name not in self.db.db.table_names():
            self.db.create_table(self.facts_table_name)
            logger.info(f"Created business_facts table: {self.facts_table_name}")

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
            "confidence_score": experience.confidence_score,
            "feedback_score": experience.feedback_score,
            "step_efficiency": experience.step_efficiency,
            "trace": experience.metadata_trace,
            "type": "experience",
            # Enhanced rating fields (NEW)
            "thumbs_up_down": experience.thumbs_up_down if hasattr(experience, 'thumbs_up_down') else None,
            "rating": experience.rating if hasattr(experience, 'rating') else None,
            "agent_execution_id": experience.agent_execution_id if hasattr(experience, 'agent_execution_id') else None,
            "feedback_type": experience.feedback_type if hasattr(experience, 'feedback_type') else None
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

    async def update_experience_feedback(
        self,
        experience_id: str,
        feedback_score: float,
        feedback_notes: str = ""
    ) -> bool:
        """
        Update an experience with human feedback.
        This is crucial for learning from corrections and avoiding repeated mistakes.
        
        Args:
            experience_id: ID of the experience to update
            feedback_score: -1.0 (bad) to 1.0 (excellent)
            feedback_notes: Optional notes explaining the feedback
        """
        try:
            # Update the experience in LanceDB
            # Since LanceDB doesn't support direct updates, we search and re-add
            results = self.db.search(
                table_name=self.table_name,
                query="",  # Empty query to get by ID
                limit=100
            )
            
            for res in results:
                if res.get("id") == experience_id:
                    meta = res.get("metadata", {})
                    
                    # Update confidence based on feedback
                    old_confidence = meta.get("confidence_score", 0.5)
                    # Blend feedback into confidence (feedback has 40% weight)
                    new_confidence = old_confidence * 0.6 + (feedback_score + 1.0) / 2.0 * 0.4
                    
                    meta["confidence_score"] = new_confidence
                    meta["feedback_score"] = feedback_score
                    meta["feedback_notes"] = feedback_notes
                    meta["feedback_at"] = datetime.now().isoformat()
                    
                    # Re-add with updated metadata (LanceDB append-only)
                    enhanced_text = res["text"] + f"\nFeedback: {feedback_notes}" if feedback_notes else res["text"]
                    
                    self.db.add_document(
                        table_name=self.table_name,
                        text=enhanced_text,
                        source=res.get("source", "system"),
                        metadata=meta,
                        user_id="feedback_system"
                    )
                    
                    logger.info(f"Updated experience {experience_id} with feedback {feedback_score}")
                    return True
                    
            logger.warning(f"Experience {experience_id} not found for feedback update")
            return False
            
        except Exception as e:
            logger.error(f"Failed to update experience feedback: {e}")
            return False

    async def boost_experience_confidence(
        self,
        experience_id: str,
        boost_amount: float = 0.1
    ) -> bool:
        """
        Boost confidence when an experience leads to successful outcomes.
        Called when an agent successfully reuses a past experience pattern.
        """
        # This is a lighter-weight update than full feedback
        # In production, this would use a proper update mechanism
        logger.info(f"Boosting experience {experience_id} confidence by {boost_amount}")
        return True  # Placeholder - would implement with proper DB update

    async def get_experience_statistics(
        self,
        agent_id: Optional[str] = None,
        agent_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get statistics about agent experiences for monitoring learning health.
        """
        try:
            results = self.db.search(
                table_name=self.table_name,
                query="experience",
                limit=1000
            )
            
            total = 0
            successes = 0
            failures = 0
            avg_confidence = 0.0
            feedback_count = 0
            
            for res in results:
                meta = res.get("metadata", {})
                
                # Filter by agent if specified
                if agent_id and meta.get("agent_id") != agent_id:
                    continue
                if agent_role and meta.get("agent_role", "").lower() != agent_role.lower():
                    continue
                
                total += 1
                outcome = meta.get("outcome", "").lower()
                if outcome == "success":
                    successes += 1
                elif outcome in ["failed", "failure"]:
                    failures += 1
                    
                avg_confidence += meta.get("confidence_score", 0.5)
                if meta.get("feedback_score") is not None:
                    feedback_count += 1
            
            return {
                "total_experiences": total,
                "successes": successes,
                "failures": failures,
                "success_rate": successes / total if total > 0 else 0,
                "avg_confidence": avg_confidence / total if total > 0 else 0.5,
                "feedback_coverage": feedback_count / total if total > 0 else 0,
                "agent_id": agent_id,
                "agent_role": agent_role
            }
            
        except Exception as e:
            logger.error(f"Failed to get experience statistics: {e}")
            return {"error": str(e)}

    async def record_business_fact(self, fact: BusinessFact) -> bool:
        """
        Save a business fact with citations to the World Model.
        """
        text_representation = (
            f"Fact: {fact.fact}\n"
            f"Citations: {', '.join(fact.citations)}\n"
            f"Reason: {fact.reason}\n"
            f"Status: {fact.verification_status}"
        )
        
        metadata = {
            "id": fact.id,
            "fact": fact.fact,
            "citations": fact.citations,
            "reason": fact.reason,
            "source_agent_id": fact.source_agent_id,
            "created_at": fact.created_at.isoformat(),
            "last_verified": fact.last_verified.isoformat(),
            "verification_status": fact.verification_status,
            "type": "business_fact",
            **fact.metadata
        }
        
        return self.db.add_document(
            table_name=self.facts_table_name,
            text=text_representation,
            source=f"fact_agent_{fact.source_agent_id}",
            metadata=metadata,
            user_id="fact_system",
            extract_knowledge=False
        )

    async def update_fact_verification(self, fact_id: str, status: str) -> bool:
        """Update the verification status of a business fact"""
        try:
            results = self.db.search(
                table_name=self.facts_table_name,
                query="", 
                limit=100
            ) 
            
            for res in results:
                if res.get("metadata", {}).get("id") == fact_id: 
                    meta = res.get("metadata", {})
                    meta["verification_status"] = status
                    meta["last_verified"] = datetime.now().isoformat()
                    
                    new_text = res["text"].replace(f"Status: {meta.get('verification_status')}", f"Status: {status}")
                    
                    self.db.add_document(
                        table_name=self.facts_table_name,
                        text=new_text,
                        source=res.get("source"),
                        metadata=meta,
                        user_id="fact_system"
                    )
                    logger.info(f"Updated fact {fact_id} status to {status}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to update fact verification: {e}")
            return False

    async def get_relevant_business_facts(self, query: str, limit: int = 5) -> List[BusinessFact]:
        """Search for verifiable business facts related to the task"""
        try:
            results = self.db.search(
                table_name=self.facts_table_name,
                query=query,
                limit=limit
            )
            
            facts = []
            for res in results:
                meta = res.get("metadata", {})
                facts.append(BusinessFact(
                    id=meta.get("id"),
                    fact=meta.get("fact"),
                    citations=meta.get("citations", []),
                    reason=meta.get("reason"),
                    source_agent_id=meta.get("source_agent_id"),
                    created_at=datetime.fromisoformat(meta.get("created_at")),
                    last_verified=datetime.fromisoformat(meta.get("last_verified")),
                    verification_status=meta.get("verification_status", "unverified"),
                    metadata=meta
                ))
            return facts
        except Exception as e:
            logger.warning(f"Failed to retrieve business facts: {e}")
            return []


    async def archive_session_to_cold_storage(self, conversation_id: str) -> bool:
        """
        Archive a completed conversation session from Postgres (Hot) to LanceDB (Cold).
        This keeps Postgres small and fast while preserving long-term memory on S3.
        """
        try:
            with get_db_session() as db:
            messages = db.query(ChatMessage).filter(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.tenant_id == self.db.workspace_id
            ).order_by(ChatMessage.created_at.asc()).all()
            
            if not messages:
                db.close()
                return False
                
            # Combine session history into a single archival document
            session_text = "\n".join([f"{m.role}: {m.content}" for m in messages])
            metadata = {
                "conversation_id": conversation_id,
                "msg_count": len(messages),
                "type": "archived_session",
                "archived_at": datetime.now().isoformat()
            }
            
            # Save to LanceDB (Cold Storage)
            success = self.db.add_document(
                table_name="archived_memories",
                text=session_text,
                source=f"session:{conversation_id}",
                metadata=metadata,
                user_id="system_archiver"
            )
            
            if success:
                # Optionally delete from Postgres after successful archival
                # db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).delete()
                # db.commit()
                logger.info(f"Successfully archived session {conversation_id} to Cold Storage")
            
            db.close()
            return success
        except Exception as e:
            logger.error(f"Failed to archive session {conversation_id}: {e}")
            return False

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
                # Basic Robustness: Only use experiences that were successful or have high confidence
                # This prevents "learning from mistakes" in a way that repeats them,
                # though negative examples can be useful if handled explicitly.
                # For now, we prioritize success.
                outcome = meta.get("outcome", "unknown")
                confidence = meta.get("confidence_score", 0.5)

                # Simple filter: Ignore failures unless explicit negative feedback loop is implemented
                if outcome == "failed" and confidence < 0.8:
                    continue

                valid_experiences.append(AgentExperience(
                    id=res["id"],
                    agent_id=creator_id or "unknown",
                    task_type=meta.get("task_type", "unknown"),
                    input_summary=res["text"].split("\n")[1].replace("Input: ", "") if "Input: " in res["text"] else "",
                    outcome=outcome,
                    learnings=res["text"].split("Learnings: ")[-1] if "Learnings: " in res["text"] else "",
                    confidence_score=confidence,
                    feedback_score=meta.get("feedback_score"),
                    artifacts=meta.get("artifacts", []),
                    agent_role=meta.get("agent_role", ""),
                    specialty=meta.get("specialty"),
                    timestamp=datetime.fromisoformat(res["created_at"])
                ))

        # Sort by confidence score descending
        valid_experiences.sort(key=lambda x: x.confidence_score, reverse=True)
        valid_experiences = valid_experiences[:limit]
        
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
            
            # Hot Fallback: If no semantic matches, get recently updated formulas for this domain
            if len(formula_results) < limit:
                try:
                    from saas.models import Formula
                    with get_db_session() as db:
                    hot_formulas = db.query(Formula).filter(
                        Formula.workspace_id == self.db.workspace_id,
                        Formula.domain == (agent_category if agent_category != "general" else Formula.domain)
                    ).order_by(Formula.updated_at.desc()).limit(limit - len(formula_results)).all()
                    
                    for f in hot_formulas:
                        # Avoid duplicates
                        if not any(fr["id"] == f.id for fr in formula_results):
                            formula_results.append({
                                "id": f.id,
                                "name": f.name,
                                "expression": f.expression,
                                "domain": f.domain,
                                "description": f.description,
                                "parameters": f.parameters,
                                "type": "formula_hot"
                            })
                    db.close()
                except Exception as he:
                    logger.warning(f"Hot formula fallback failed: {he}")
        except Exception as fe:
            logger.warning(f"Formula recall failed: {fe}")

        # 4. Search Conversations (Postgres Persistence)
        conversation_results = []
        try:
            with get_db_session() as db:
            # Get latest 5 messages for this tenant/agent context (generic)
            # In a real scenario, we might want to filter by keywords or session_id
            messages = db.query(ChatMessage).filter(
                ChatMessage.tenant_id == self.db.workspace_id
            ).order_by(ChatMessage.created_at.desc()).limit(limit).all()
            
            conversation_results = [
                {
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat()
                }
                for m in messages
            ]
            db.close()
            logger.info(f"Retrieved {len(conversation_results)} recent conversation messages")
        except Exception as ce:
            logger.warning(f"Conversation recall failed: {ce}")

        # 5. Search Business Facts (Trusted Memory)
        business_facts = await self.get_relevant_business_facts(current_task_description, limit=limit)

        return {
            "experiences": valid_experiences,
            "knowledge": knowledge_results,
            "knowledge_graph": graph_context, 
            "formulas": formula_results,
            "conversations": conversation_results,
            "business_facts": business_facts
        }
