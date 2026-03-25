from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel

from core.database import get_db_session
from core.lancedb_handler import LanceDBHandler, get_lancedb_handler
from core.models import AgentRegistry, AgentStatus, ChatMessage

from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class DetailLevel(str, Enum):
    """Detail level for episode recall - controls token usage"""
    SUMMARY = "summary"   # ~50 tokens: canvas type + summary + has_errors
    STANDARD = "standard" # ~200 tokens: summary + visual_elements + data
    FULL = "full"         # ~500 tokens: standard + full_state + audit_trail

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
    
    # Governance & Verification (Phase 189 Alignment)
    source_agent_id: str
    verification_status: str = "pending" # pending, verified, rejected
    created_at: datetime = datetime.now(timezone.utc)
    last_verified: datetime = datetime.now(timezone.utc)
    metadata: Dict[str, Any] = {}

@dataclass
class SkillRecommendation:
    """Recommendation for an OpenClaw skill based on task context"""
    skill_id: str
    skill_name: Optional[str]
    success_rate: float
    execution_count: int
    last_executed_at: Optional[datetime]
    reason: str

class WorldModelService:
    def __init__(self, workspace_id: str = "default", tenant_id: Optional[str] = None):
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id or "default"
        self.db = get_lancedb_handler(workspace_id=workspace_id, tenant_id=self.tenant_id)
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
        try:
            # Search for the experience by ID
            results = self.db.search(
                table_name=self.table_name,
                query="",  # Empty query to get all records
                limit=1000  # Increase limit to find the target experience
            )

            for res in results:
                if res.get("id") == experience_id:
                    meta = res.get("metadata", {})

                    # Boost confidence score (cap at 1.0)
                    old_confidence = meta.get("confidence_score", 0.5)
                    new_confidence = min(1.0, old_confidence + boost_amount)

                    # Track boost count
                    boost_count = meta.get("boost_count", 0) + 1

                    meta["confidence_score"] = new_confidence
                    meta["boost_count"] = boost_count
                    meta["last_boosted_at"] = datetime.now().isoformat()

                    # Re-add with updated metadata (LanceDB append-only)
                    self.db.add_document(
                        table_name=self.table_name,
                        text=res.get("text", ""),
                        source=res.get("source", "system"),
                        metadata=meta,
                        user_id="confidence_boost_system"
                    )

                    logger.info(
                        f"Boosted experience {experience_id} confidence: "
                        f"{old_confidence:.3f} -> {new_confidence:.3f} "
                        f"(boost #{boost_count})"
                    )
                    return True

            logger.warning(f"Experience {experience_id} not found for confidence boost")
            return False

        except Exception as e:
            logger.error(f"Failed to boost experience confidence: {e}")
            return False

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
        """
        Update the verification status of a business fact.

        This method deletes the old fact document and adds a new one with updated status.
        Uses skip_ai_triggers=True to prevent infinite loops from system-generated updates.
        """
        try:
            # Search for the fact document
            results = self.db.search(
                table_name=self.facts_table_name,
                query="",
                limit=100
            )

            fact_doc = None
            for res in results:
                if res.get("metadata", {}).get("id") == fact_id:
                    fact_doc = res
                    break

            if not fact_doc:
                logger.warning(f"Fact {fact_id} not found for update")
                return False

            meta = fact_doc.get("metadata", {})
            old_doc_id = fact_doc.get("id")
            old_status = meta.get("verification_status", "unverified")

            # Skip if status hasn't changed
            if old_status == status:
                return True

            # Update metadata
            meta["verification_status"] = status
            meta["last_verified"] = datetime.now().isoformat()

            # Update text with new status
            new_text = fact_doc["text"].replace(f"Status: {old_status}", f"Status: {status}")

            # Delete old document FIRST to prevent duplicates
            if old_doc_id:
                try:
                    table = self.db.get_table(self.facts_table_name)
                    if table:
                        table.delete(f"id = '{old_doc_id}'")
                        logger.debug(f"Deleted old fact document {old_doc_id}")
                except Exception as delete_err:
                    logger.warning(f"Failed to delete old document {old_doc_id}: {delete_err}")

            # Add updated document with AI triggers skipped to prevent loops
            success = self.db.add_document(
                table_name=self.facts_table_name,
                text=new_text,
                source=fact_doc.get("source"),
                metadata=meta,
                user_id="fact_system",
                extract_knowledge=False,
                skip_ai_triggers=True  # Critical: prevents infinite loop
            )

            if success:
                logger.info(f"Updated fact {fact_id} status to {status}")
            else:
                logger.error(f"Failed to add updated document for fact {fact_id}")

            return success
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

            # Deduplicate by fact ID, keeping the most recent version
            fact_map = {}  # fact_id -> (last_verified, BusinessFact)

            for res in results:
                meta = res.get("metadata", {})
                fact_id = meta.get("id")

                fact = BusinessFact(
                    id=fact_id,
                    fact=meta.get("fact"),
                    citations=meta.get("citations", []),
                    reason=meta.get("reason"),
                    source_agent_id=meta.get("source_agent_id"),
                    created_at=datetime.fromisoformat(meta.get("created_at")),
                    last_verified=datetime.fromisoformat(meta.get("last_verified")),
                    verification_status=meta.get("verification_status", "unverified"),
                    metadata=meta
                )

                # Keep only the most recent version of each fact
                if fact_id not in fact_map or fact.last_verified > fact_map[fact_id][0]:
                    fact_map[fact_id] = (fact.last_verified, fact)

            # Return unique facts sorted by relevance (original search order)
            unique_facts = [fact for _, fact in list(fact_map.values())]
            return unique_facts[:limit]
        except Exception as e:
            logger.warning(f"Failed to retrieve business facts: {e}")
            return []

    async def list_all_facts(
        self,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 100
    ) -> List[BusinessFact]:
        """
        List all business facts with optional filters.

        Args:
            status: Filter by verification status
            domain: Filter by domain
            limit: Maximum number of facts to return

        Returns:
            List of BusinessFact objects
        """
        try:
            # Search with empty query to get all facts
            results = self.db.search(
                table_name=self.facts_table_name,
                query="",
                limit=limit
            )

            # Deduplicate by fact ID, keeping the most recent version
            # (necessary because update_fact_verification creates new documents)
            fact_map = {}  # fact_id -> (last_verified, BusinessFact)

            for res in results:
                meta = res.get("metadata", {})
                fact_id = meta.get("id")

                # Apply filters
                if status and meta.get("verification_status") != status:
                    continue
                if domain and meta.get("domain") != domain:
                    continue

                fact = BusinessFact(
                    id=fact_id,
                    fact=meta.get("fact"),
                    citations=meta.get("citations", []),
                    reason=meta.get("reason"),
                    source_agent_id=meta.get("source_agent_id"),
                    created_at=datetime.fromisoformat(meta.get("created_at")),
                    last_verified=datetime.fromisoformat(meta.get("last_verified")),
                    verification_status=meta.get("verification_status", "unverified"),
                    metadata=meta
                )

                # Keep only the most recent version of each fact
                if fact_id not in fact_map or fact.last_verified > fact_map[fact_id][0]:
                    fact_map[fact_id] = (fact.last_verified, fact)

            # Return unique facts
            return [fact for _, fact in fact_map.values()]
        except Exception as e:
            logger.warning(f"Failed to list business facts: {e}")
            return []

    async def get_fact_by_id(self, fact_id: str) -> Optional[BusinessFact]:
        """
        Get a specific business fact by ID.

        Args:
            fact_id: The fact ID to retrieve

        Returns:
            BusinessFact if found, None otherwise
        """
        try:
            results = self.db.search(
                table_name=self.facts_table_name,
                query="",
                limit=1000  # Higher limit to find the fact
            )

            # Handle duplicates - return the most recent version
            most_recent_fact = None
            most_recent_verified = None

            for res in results:
                meta = res.get("metadata", {})
                if meta.get("id") == fact_id:
                    fact = BusinessFact(
                        id=meta.get("id"),
                        fact=meta.get("fact"),
                        citations=meta.get("citations", []),
                        reason=meta.get("reason"),
                        source_agent_id=meta.get("source_agent_id"),
                        created_at=datetime.fromisoformat(meta.get("created_at")),
                        last_verified=datetime.fromisoformat(meta.get("last_verified")),
                        verification_status=meta.get("verification_status", "unverified"),
                        metadata=meta
                    )

                    # Keep the most recent version
                    if most_recent_fact is None or (most_recent_verified and fact.last_verified > most_recent_verified):
                        most_recent_fact = fact
                        most_recent_verified = fact.last_verified

            return most_recent_fact
            return None
        except Exception as e:
            logger.warning(f"Failed to get fact by ID: {e}")
            return None

    async def delete_fact(self, fact_id: str) -> bool:
        """
        Soft delete a business fact by marking as deleted.

        Args:
            fact_id: The fact ID to delete

        Returns:
            True if successful, False otherwise
        """
        return await self.update_fact_verification(fact_id, "deleted")

    async def bulk_record_facts(self, facts: List[BusinessFact]) -> int:
        """
        Record multiple business facts in bulk.

        Args:
            facts: List of BusinessFact objects to record

        Returns:
            Number of facts successfully recorded
        """
        success_count = 0
        for fact in facts:
            if await self.record_business_fact(fact):
                success_count += 1
        return success_count

    async def record_episode(
        self,
        episode_id: str,
        agent_id: str,
        tenant_id: str,
        task_description: str,
        outcome: str,
        learnings: str,
        agent_role: str,
        maturity_at_time: str,
        constitutional_score: float = 1.0,
        human_intervention_count: int = 0,
        confidence_score: float = 0.5,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Record an episode to LanceDB for long-term retention and semantic search.
        """
        text_representation = (
            f"Episode: {task_description}\n"
            f"Outcome: {outcome}\n"
            f"Learnings: {learnings}\n"
            f"Maturity: {maturity_at_time}\n"
            f"Constitutional Score: {constitutional_score:.2f}\n"
            f"Interventions: {human_intervention_count}"
        )

        episode_metadata = {
            "episode_id": episode_id,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "task_type": "episode",
            "outcome": outcome,
            "agent_role": agent_role,
            "maturity_at_time": maturity_at_time,
            "constitutional_score": constitutional_score,
            "human_intervention_count": human_intervention_count,
            "confidence_score": confidence_score,
            "type": "episode",
            **(metadata or {})
        }

        return self.db.add_document(
            table_name="agent_episodes",
            text=text_representation,
            source=f"episode_{agent_id}",
            metadata=episode_metadata,
            user_id="episode_system",
            extract_knowledge=False
        )

    async def sync_episode_to_lancedb(
        self,
        episode_id: str,
        agent_id: str,
        tenant_id: str,
        task_description: str,
        outcome: str,
        learnings: str,
        agent_role: str,
        maturity_at_time: str,
        constitutional_score: float = 1.0,
        human_intervention_count: int = 0,
        confidence_score: float = 0.5,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Sync an episode from PostgreSQL to LanceDB.
        """
        return await self.record_episode(
            episode_id=episode_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            task_description=task_description,
            outcome=outcome,
            learnings=learnings,
            agent_role=agent_role,
            maturity_at_time=maturity_at_time,
            constitutional_score=constitutional_score,
            human_intervention_count=human_intervention_count,
            confidence_score=confidence_score,
            metadata=metadata
        )

    async def recall_episodes(
        self,
        task_description: str,
        agent_role: str,
        agent_id: Optional[str] = None,
        canvas_id: Optional[str] = None,
        min_feedback_score: Optional[float] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recall relevant episodes from LanceDB with canvas and feedback awareness.
        """
        try:
            query = f"{agent_role} {task_description}"
            results = self.db.search(
                table_name="agent_episodes",
                query=query,
                limit=limit * 2
            )

            scored_episodes = []
            for res in results:
                meta = res.get("metadata", {})
                if meta.get("agent_role") != agent_role:
                    continue
                if agent_id and meta.get("agent_id") != agent_id:
                    continue
                if meta.get("type") != "episode":
                    continue

                base_score = res.get("_score", 0.5)
                canvas_boost = 0.0
                feedback_boost = 0.0

                if canvas_id and meta.get("canvas_id") == canvas_id:
                    canvas_boost = 0.3
                    
                feedback_score = meta.get("feedback_score")
                if feedback_score is not None:
                    if feedback_score > 0.5:
                        feedback_boost = 0.2
                    elif feedback_score < -0.5:
                        feedback_boost = -0.3

                if min_feedback_score is not None and (feedback_score is None or feedback_score < min_feedback_score):
                    continue

                final_score = base_score + canvas_boost + feedback_boost
                scored_episodes.append({
                    "episode_id": meta.get("episode_id"),
                    "agent_id": meta.get("agent_id"),
                    "task_description": res.get("text", "").split("Outcome:")[0].replace("Episode: ", "").strip(),
                    "outcome": meta.get("outcome"),
                    "final_score": final_score,
                    "metadata": meta
                })

            scored_episodes.sort(key=lambda x: x["final_score"], reverse=True)
            return scored_episodes[:limit]
        except Exception as e:
            logger.warning(f"Failed to recall episodes: {e}")
            return []

    async def archive_session_to_cold_storage_with_cleanup(
        self,
        conversation_id: str,
        retention_days: int = 30,
        verify_before_delete: bool = True
    ) -> dict:
        """
        Archive a session to LanceDB and optionally hard delete from PostgreSQL after retention period.

        This is a safer alternative that:
        1. Verifies archival success before deletion
        2. Implements soft delete with retention period
        3. Creates audit trail for deleted records
        4. Allows rollback within retention period

        Args:
            conversation_id: Session ID to archive
            retention_days: Days to keep soft-deleted records before hard delete
            verify_before_delete: Verify LanceDB archival before PostgreSQL deletion

        Returns:
            Dictionary with status, audit_id, and details
        """
        audit_id = f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{conversation_id[:8]}"
        result = {
            "audit_id": audit_id,
            "conversation_id": conversation_id,
            "status": "failed",
            "archived": False,
            "soft_deleted": False,
            "hard_deleted": False,
            "error": None
        }

        try:
            with get_db_session() as db:
                # Step 1: Archive to LanceDB
                logger.info(f"[{audit_id}] Starting archival with cleanup for session {conversation_id}")

                messages = db.query(ChatMessage).filter(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.tenant_id == self.db.workspace_id
                ).order_by(ChatMessage.created_at.asc()).all()

                if not messages:
                    result["error"] = "No messages found"
                    return result

                # Combine session history
                session_text = "\n".join([f"{m.role}: {m.content}" for m in messages])
                metadata = {
                    "conversation_id": conversation_id,
                    "msg_count": len(messages),
                    "type": "archived_session",
                    "archived_at": datetime.now(timezone.utc).isoformat(),
                    "audit_id": audit_id,
                    "retention_days": retention_days
                }

                # Save to LanceDB
                lancedb_success = self.db.add_document(
                    table_name="archived_memories",
                    text=session_text,
                    source=f"session:{conversation_id}",
                    metadata=metadata,
                    user_id="system_archiver"
                )

                if not lancedb_success:
                    result["error"] = "Failed to archive to LanceDB"
                    return result

                result["archived"] = True
                logger.info(f"[{audit_id}] ✓ Archived to LanceDB")

                # Step 2: Verify archival (if requested)
                if verify_before_delete:
                    # Search for the archived document
                    verification_results = self.db.search(
                        table_name="archived_memories",
                        query=f"conversation_id:{conversation_id}",
                        limit=1
                    )

                    if not verification_results:
                        result["error"] = "Verification failed: document not found in LanceDB"
                        return result

                    logger.info(f"[{audit_id}] ✓ Verified archival in LanceDB")

                # Step 3: Soft delete (mark with metadata)
                for msg in messages:
                    msg.metadata_json = msg.metadata_json or {}
                    msg.metadata_json.update({
                        "_archived": True,
                        "_archived_at": datetime.now(timezone.utc).isoformat(),
                        "_archived_to_lancedb": True,
                        "_audit_id": audit_id,
                        "_retention_until": (datetime.now(timezone.utc) + timedelta(days=retention_days)).isoformat()
                    })

                db.commit()
                result["soft_deleted"] = True
                logger.info(f"[{audit_id}] ✓ Soft deleted {len(messages)} messages")

                # Step 4: Schedule hard delete after retention period
                result["status"] = "success"
                result["scheduled_for_hard_delete"] = (datetime.now(timezone.utc) + timedelta(days=retention_days)).isoformat()

                logger.info(f"[{audit_id}] ✓ Archival complete. Hard delete scheduled for {result['scheduled_for_hard_delete']}")

            return result

        except Exception as e:
            logger.error(f"[{audit_id}] Failed: {e}")
            result["error"] = str(e)
            return result

    async def recover_archived_session(self, conversation_id: str) -> dict:
        """
        Recover a soft-deleted session from archival status.
        Removes the archived flags and restores the messages to active state.
        """
        result = {
            "conversation_id": conversation_id,
            "status": "failed",
            "recovered_count": 0,
            "error": None
        }

        try:
            with get_db_session() as db:
                messages = db.query(ChatMessage).filter(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.tenant_id == self.db.workspace_id,
                    ChatMessage.metadata_json.is_not(None)
                ).all()

                # Filter manually for those having _archived key
                archived_messages = [m for m in messages if m.metadata_json.get('_archived')]

                if not archived_messages:
                    result["error"] = "No archived messages found"
                    return result

                # Remove archival flags
                for msg in archived_messages:
                    # Keep audit trail but remove archived status
                    msg.metadata_json["_recovered"] = True
                    msg.metadata_json["_recovered_at"] = datetime.now(timezone.utc).isoformat()
                    # Remove the _archived flag
                    msg.metadata_json.pop("_archived", None)

                db.commit()
                result["status"] = "success"
                result["recovered_count"] = len(archived_messages)

                logger.info(f"Recovered {len(archived_messages)} messages from session {conversation_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to recover session {conversation_id}: {e}")
            result["error"] = str(e)
            return result

    async def hard_delete_archived_sessions(self, older_than_days: int = 30) -> dict:
        """
        Permanently delete sessions that have been soft-deleted for longer than retention.
        """
        result = {
            "status": "failed",
            "deleted_count": 0,
            "error": None
        }

        try:
            with get_db_session() as db:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)

                # Find messages that have been archived
                all_archived = db.query(ChatMessage).filter(
                    ChatMessage.tenant_id == self.db.workspace_id,
                    ChatMessage.metadata_json.is_not(None)
                ).all()

                messages_past_retention = []
                for msg in all_archived:
                    if not msg.metadata_json.get('_archived'):
                        continue
                        
                    retention_until = msg.metadata_json.get('_retention_until')
                    if retention_until:
                        try:
                            retention_date = datetime.fromisoformat(retention_until)
                            if retention_date < datetime.now(timezone.utc):
                                messages_past_retention.append(msg)
                        except (ValueError, TypeError):
                            # In case of corruption, fallback to age
                            if msg.created_at < cutoff_date:
                                messages_past_retention.append(msg)
                    elif msg.created_at < cutoff_date:
                        messages_past_retention.append(msg)

                if not messages_past_retention:
                    result["status"] = "success"
                    result["deleted_count"] = 0
                    return result

                # Perform hard delete
                count = 0
                for msg in messages_past_retention:
                    db.delete(msg)
                    count += 1

                db.commit()
                result["status"] = "success"
                result["deleted_count"] = count

                logger.info(f"Hard deleted {count} messages past retention")
            return result

        except Exception as e:
            logger.error(f"Failed to hard delete archived sessions: {e}")
            result["error"] = str(e)
            return result


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

    async def recall_experiences_with_detail(
        self,
        tenant_id: str,
        agent_role: str,
        task_description: str,
        detail_level: DetailLevel = DetailLevel.SUMMARY,
        agent_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recall experiences with configurable detail level.
        Uses specialized progressive queries from EpisodeService.
        """
        from core.service_factory import ServiceFactory
        
        with get_db_session() as db:
            episode_service = ServiceFactory.get_episode_service(db, workspace_id=tenant_id)
            
            # Use raw SQL for performant detail retrieval
            from sqlalchemy import text
            from core.episode_service import PROGRESSIVE_QUERIES
            
            query_sql = PROGRESSIVE_QUERIES.get(detail_level)
            if not query_sql:
                return []
                
            result = db.execute(
                text(query_sql),
                {"agent_id": agent_id, "limit": limit}
            )

            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]

    async def archive_episode_to_cold_storage(
        self,
        episode_id: str,
        agent_id: str,
        tenant_id: str,
        task_description: str,
        outcome: str,
        learnings: str,
        agent_role: str,
        maturity_at_time: str,
        constitutional_score: float = 1.0,
        human_intervention_count: int = 0,
        confidence_score: float = 0.5
    ) -> bool:
        """
        Archive an episode from PostgreSQL hot storage to LanceDB cold storage.
        """
        try:
            # Reuse sync_episode_to_lancedb implementation
            # Note: Upstream generic record_episode might not exist in the same way,
            # but we'll ensure consistency with EpisodeService.
            success = await self.sync_episode_to_lancedb(
                episode_id=episode_id,
                agent_id=agent_id,
                tenant_id=tenant_id,
                task_description=task_description,
                outcome=outcome,
                learnings=learnings,
                agent_role=agent_role,
                maturity_at_time=maturity_at_time,
                constitutional_score=constitutional_score,
                human_intervention_count=human_intervention_count,
                confidence_score=confidence_score
            )
            return success
        except Exception as e:
            logger.error(f"Error archiving episode {episode_id}: {e}")
            return False

    async def get_recent_episodes(
        self,
        agent_id: str,
        tenant_id: str,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Get recent episodes for graduation readiness."""
        try:
            from core.models import AgentEpisode
            with get_db_session() as db:
                episodes = db.query(AgentEpisode).filter(
                    AgentEpisode.agent_id == agent_id,
                    AgentEpisode.tenant_id == tenant_id
                ).order_by(AgentEpisode.started_at.desc()).limit(limit).all()

                return [
                    {
                        "episode_id": ep.id,
                        "task_description": ep.task_description,
                        "outcome": ep.outcome,
                        "success": ep.success,
                        "maturity_at_time": ep.maturity_at_time,
                        "constitutional_score": ep.constitutional_score,
                        "human_intervention_count": ep.human_intervention_count,
                        "confidence_score": ep.confidence_score,
                        "step_efficiency": ep.step_efficiency,
                        "started_at": ep.started_at.isoformat() if ep.started_at else None,
                        "completed_at": ep.completed_at.isoformat() if ep.completed_at else None
                    }
                    for ep in episodes
                ]
        except Exception as e:
            logger.warning(f"Failed to get recent episodes: {e}")
            return []

    def get_episode_feedback_for_decision(
        self,
        episode_ids: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve complete feedback records for multiple episodes."""
        from core.models import EpisodeFeedback
        if not episode_ids:
            return {}

        try:
            with get_db_session() as db:
                feedback_records = db.query(EpisodeFeedback).filter(
                    EpisodeFeedback.episode_id.in_(episode_ids)
                ).all()

                result = {}
                for f in feedback_records:
                    if f.episode_id not in result:
                        result[f.episode_id] = []

                    result[f.episode_id].append({
                        "id": f.id,
                        "feedback_score": f.feedback_score,
                        "feedback_notes": f.feedback_notes,
                        "feedback_category": f.feedback_category,
                        "provider_id": f.provider_id,
                        "provider_type": f.provider_type,
                        "provided_at": f.provided_at.isoformat() if f.provided_at else None
                    })
                return result
        except Exception as e:
            logger.error(f"Failed to get episode feedback for decision: {e}")
            return {}


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
                    from core.models import Formula
                    with get_db_session() as db:
                        hot_formulas = db.query(Formula).filter(
                            Formula.tenant_id == self.db.workspace_id,
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

        # 6. Search Episodes (NEW)
        episodes_result = []
        try:
            from core.episode_retrieval_service import EpisodeRetrievalService

            with get_db_session() as db:
                episode_service = EpisodeRetrievalService(db)
                episodes_response = await episode_service.retrieve_contextual(
                    agent_id=agent.id,
                    current_task=current_task_description,
                    limit=limit
                )
                episodes_result = episodes_response.get("episodes", [])

                # 7. Enrich episodes with canvas and feedback context (ALWAYS)
                # This happens for EVERY episode recall, not just canvas-specific tasks
                enriched_episodes = []
                for episode_result in episodes_result:
                    episode_id = episode_result.get("id")
                    if not episode_id:
                        enriched_episodes.append(episode_result)
                        continue

                    # ALWAYS fetch canvas context (if available)
                    canvas_context = []
                    if episode_result.get("canvas_ids"):
                        try:
                            canvas_context = await episode_service._fetch_canvas_context(
                                episode_result["canvas_ids"]
                            )
                        except Exception as ce:
                            logger.warning(f"Canvas context fetch failed for episode {episode_id}: {ce}")

                    # ALWAYS fetch feedback context (if available)
                    feedback_context = []
                    if episode_result.get("feedback_ids"):
                        try:
                            feedback_context = await episode_service._fetch_feedback_context(
                                episode_result["feedback_ids"]
                            )
                        except Exception as fe:
                            logger.warning(f"Feedback context fetch failed for episode {episode_id}: {fe}")

                    # Enrich episode with full context
                    enriched_episodes.append({
                        **episode_result,
                        "canvas_context": canvas_context,
                        "feedback_context": feedback_context
                    })

                # Replace with enriched episodes
                episodes_result = enriched_episodes

        except Exception as ee:
            logger.warning(f"Episode recall failed: {ee}")

        return {
            "experiences": valid_experiences,
            "knowledge": knowledge_results,
            "knowledge_graph": graph_context,
            "formulas": formula_results,
            "conversations": conversation_results,
            "business_facts": business_facts,
            "episodes": episodes_result  # NEW - Enriched with canvas/feedback
        }

    def _extract_canvas_insights(self, enriched_episodes: List[Any]) -> Dict[str, Any]:
        """
        Extract actionable insights from canvas context in episodes.

        Analyzes canvas presentations and user feedback to derive patterns
        that can inform agent decision-making.

        Args:
            enriched_episodes: List of episodes with canvas_context and feedback_context

        Returns:
            {
                "canvas_type_counts": Dict[str, int],
                "user_actions": Dict[str, int],
                "high_engagement_canvases": List[Dict],
                "preferred_canvas_types": List[str],
                "user_interaction_patterns": Dict[str, List[str]]
            }
        """
        insights = {
            "canvas_type_counts": {},
            "user_actions": {},
            "high_engagement_canvases": [],
            "preferred_canvas_types": [],
            "user_interaction_patterns": {
                "closes_quickly": [],
                "engages": [],
                "submits": []
            }
        }

        try:
            for episode in enriched_episodes:
                canvas_context = episode.get("canvas_context", [])
                feedback_context = episode.get("feedback_context", [])

                for canvas in canvas_context:
                    canvas_type = canvas.get("canvas_type")
                    action = canvas.get("action")

                    if not canvas_type:
                        continue

                    # Track canvas type usage
                    insights["canvas_type_counts"][canvas_type] = \
                        insights["canvas_type_counts"].get(canvas_type, 0) + 1

                    # Track user actions
                    if action:
                        insights["user_actions"][action] = \
                            insights["user_actions"].get(action, 0) + 1

                        # Track interaction patterns
                        if action == "close":
                            insights["user_interaction_patterns"]["closes_quickly"].append(canvas_type)
                        elif action in ["present", "update"]:
                            insights["user_interaction_patterns"]["engages"].append(canvas_type)
                        elif action == "submit":
                            insights["user_interaction_patterns"]["submits"].append(canvas_type)

                # Track high-engagement canvases (positive feedback)
                if feedback_context and canvas_context:
                    # Calculate average feedback rating
                    ratings = [
                        f.get("rating", 3)
                        for f in feedback_context
                        if f.get("rating") is not None
                    ]

                    if ratings:
                        avg_feedback = sum(ratings) / len(ratings)

                        if avg_feedback >= 4:
                            # This episode had high engagement
                            for canvas in canvas_context:
                                insights["high_engagement_canvases"].append({
                                    "canvas_id": canvas.get("id"),
                                    "canvas_type": canvas.get("canvas_type"),
                                    "action": canvas.get("action"),
                                    "avg_feedback": avg_feedback
                                })

            # Determine preferred canvas types (most used with positive engagement)
            type_counts = insights["canvas_type_counts"]
            if type_counts:
                # Sort by count descending
                sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
                insights["preferred_canvas_types"] = [t[0] for t in sorted_types]

        except Exception as e:
            logger.warning(f"Failed to extract canvas insights: {e}")

        return insights

    async def recommend_skills_for_task(
        self,
        task_description: str,
        agent_id: str,
        tenant_id: str,
        limit: int = 5
    ) -> List[SkillRecommendation]:
        """
        Recommend OpenClaw skills based on historical performance for similar tasks.

        Uses semantic search to find similar past tasks and analyzes which
        OpenClaw skills were used successfully. Ranks skills by:
        1. Success rate (successful executions / total)
        2. Execution count (higher = more reliable)
        3. Semantic similarity (from vector search)

        Args:
            task_description: Description of the current task
            agent_id: ID of the agent
            tenant_id: ID of the tenant
            limit: Maximum number of recommendations to return

        Returns:
            List of SkillRecommendation objects sorted by relevance
        """
        try:
            from core.models import AgentRegistry, Skill
            
            # Identify agent role
            with get_db_session() as db:
                agent = db.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id,
                    AgentRegistry.tenant_id == tenant_id
                ).first()

                if not agent:
                    logger.warning(f"Agent {agent_id} not found for tenant {tenant_id}")
                    return []

                agent_role = agent.category or "general"

                # Step 1: Recall semantically similar episodes
                similar_episodes = await self.recall_episodes(
                    task_description=task_description,
                    agent_role=agent_role,
                    agent_id=agent_id,
                    limit=limit * 3
                )

                # Step 2: Filter for OpenClaw skill episodes
                skill_episodes = []
                for ep in similar_episodes:
                    meta = ep.get("metadata", {})
                    if meta.get("skill_type") == "openclaw":
                        sid = meta.get("skill_id")
                        if sid:
                            skill_episodes.append({
                                "skill_id": sid,
                                "outcome": ep.get("outcome"),
                                "final_score": ep.get("final_score", 0.5)
                            })

                if not skill_episodes:
                    return []

                # Step 3: Aggregate statistics
                skill_stats = {}
                for ep in skill_episodes:
                    sid = ep["skill_id"]
                    if sid not in skill_stats:
                        skill_stats[sid] = {"total": 0, "success": 0}
                    skill_stats[sid]["total"] += 1
                    if ep["outcome"] == "success":
                        skill_stats[sid]["success"] += 1

                # Step 4: Generate recommendations
                recommendations = []
                for sid, stats in skill_stats.items():
                    skill_obj = db.query(Skill).filter(Skill.id == sid).first()
                    success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
                    
                    recommendations.append(SkillRecommendation(
                        skill_id=sid,
                        skill_name=skill_obj.name if skill_obj else None,
                        success_rate=float(f"{success_rate:.4f}"),
                        execution_count=stats["total"],
                        last_executed_at=None,
                        reason=f"Used successfully in {stats['success']} similar episodes"
                    ))

                # Step 5: Rank and return
                recommendations.sort(key=lambda x: (x.success_rate, x.execution_count), reverse=True)
                return recommendations[:limit]

        except Exception as e:
            logger.warning(f"Failed to recommend skills: {e}")
            return []

    async def validate_factual_consistency(
        self,
        experience: AgentExperience,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Validate an experience against the "Trusted Memory" (Business Facts).
        
        Identifies potential contradictions between what the agent did and
        established business policies or facts.
        """
        try:
            # 1. Get relevant business facts for this task
            relevant_facts = await self.get_relevant_business_facts(
                experience.input_summary, 
                limit=limit
            )
            
            if not relevant_facts:
                return {"status": "consistent", "conflicts": [], "reason": "No relevant facts found"}
                
            # 2. Heuristic/Semantic check for consistency
            # In a real scenario, this would use an LLM to compare experience.learnings
            # against each fact. For the port, we implement the semantic structure.
            conflicts = []
            for fact in relevant_facts:
                # Basic contradiction detection (mock/semantic placeholder)
                # If "Success" but learnings mention "Mismatch", and a fact exists...
                if "mismatch" in experience.learnings.lower() and "reconcile" in fact["fact"].lower():
                    # This is a highly simplified heuristic for the port
                    conflicts.append({
                        "fact_id": fact["id"],
                        "fact": fact["fact"],
                        "conflict_type": "potential_contradiction",
                        "severity": "medium"
                    })
            
            return {
                "status": "warning" if conflicts else "consistent",
                "conflicts": conflicts,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "fact_count": len(relevant_facts)
            }
        except Exception as e:
            logger.warning(f"Factual consistency check failed: {e}")
            return {"status": "error", "reason": str(e)}
