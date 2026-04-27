from typing import List, Dict, Any, Optional
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from dataclasses import dataclass
from enum import Enum

from core.models import AgentRegistry, AgentStatus, ChatMessage
from core.lancedb_handler import LanceDBHandler, get_lancedb_handler
from core.database import SessionLocal

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
    artifacts: Optional[List[str]] = None
    
    # TRACE Framework Metrics (Phase 6.6)
    step_efficiency: float = 1.0  # (Steps Taken / Expected Steps) - lower is better
    metadata_trace: Dict[str, Any] = {} # Detailed execution trace, plan adherence, etc.
    
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
    def __init__(self, workspace_id: Optional[str] = None):
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
            "artifacts": experience.artifacts if experience.artifacts is not None else [],
            "confidence_score": experience.confidence_score,
            "feedback_score": experience.feedback_score,
            "step_efficiency": experience.step_efficiency,
            "trace": experience.metadata_trace,
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
                    meta["feedback_at"] = datetime.now(timezone.utc).isoformat()
                    
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
                    meta["last_verified"] = datetime.now(timezone.utc).isoformat()
                    
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

    async def get_business_fact(self, fact_id: str) -> Optional[BusinessFact]:
        """Retrieve a specific business fact by ID"""
        try:
            # Direct table access for efficiency
            table = self.db.get_table(self.facts_table_name)
            if not table:
                return None
            
            # Use LanceDB filtering
            results = table.search().where(f"id == '{fact_id}'").limit(1).to_pandas()
            
            if results.empty:
                return None
                
            row = results.iloc[0]
            
            # Parse metadata
            meta = json.loads(row['metadata']) if (isinstance(row['metadata'], str) and row['metadata']) else {}
            
            # Construct BusinessFact
            return BusinessFact(
                id=row['id'],
                fact=meta.get("fact", row['text'].split('\n')[0].replace("Fact: ", "")),
                citations=meta.get("citations", []),
                reason=meta.get("reason"),
                source_agent_id=meta.get("source_agent_id"),
                created_at=datetime.fromisoformat(meta.get("created_at")),
                last_verified=datetime.fromisoformat(meta.get("last_verified")) if meta.get("last_verified") else datetime.now(timezone.utc),
                verification_status=meta.get("verification_status", "unverified"),
                metadata=meta
            )
        except Exception as e:
            logger.error(f"Failed to get business fact {fact_id}: {e}")
            return None

    async def bulk_record_facts(self, facts: List[BusinessFact]) -> int:
        """
        Store multiple extracted facts at once.
        
        Args:
            facts: List of BusinessFact objects to store
            
        Returns:
            Number of successfully stored facts
        """
        success_count = 0
        for fact in facts:
            try:
                if await self.record_business_fact(fact):
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to store fact '{fact.fact[:50]}...': {e}")
        
        logger.info(f"Bulk stored {success_count}/{len(facts)} facts")
        return success_count

    async def list_all_facts(
        self,
        status: str = None,
        domain: str = None,
        limit: int = 100
    ) -> List[BusinessFact]:
        """
        List all business facts for the workspace.
        
        Args:
            status: Optional filter by verification_status
            domain: Optional filter by domain
            limit: Maximum facts to return
            
        Returns:
            List of BusinessFact objects
        """
        try:
            # Search with empty query to get all facts
            results = self.db.search(
                table_name=self.facts_table_name,
                query="",
                limit=limit * 2  # Fetch extra for filtering
            )
            
            facts = []
            for res in results:
                meta = res.get("metadata", {})
                
                # Apply filters
                if status and meta.get("verification_status") != status:
                    continue
                if domain and meta.get("domain") != domain:
                    continue
                
                try:
                    fact = BusinessFact(
                        id=meta.get("id"),
                        fact=meta.get("fact"),
                        citations=meta.get("citations", []),
                        reason=meta.get("reason", ""),
                        source_agent_id=meta.get("source_agent_id", "system"),
                        created_at=datetime.fromisoformat(meta.get("created_at")) if meta.get("created_at") else datetime.now(timezone.utc),
                        last_verified=datetime.fromisoformat(meta.get("last_verified")) if meta.get("last_verified") else datetime.now(timezone.utc),
                        verification_status=meta.get("verification_status", "unverified"),
                        metadata={"domain": meta.get("domain", "general")}
                    )
                    facts.append(fact)
                except Exception as e:
                    logger.warning(f"Failed to parse fact: {e}")
                
                if len(facts) >= limit:
                    break
            
            return facts
            
        except Exception as e:
            logger.error(f"Failed to list facts: {e}")
            return []

    async def get_fact_by_id(self, fact_id: str) -> BusinessFact | None:
        """Get a specific fact by ID"""
        try:
            results = self.db.search(
                table_name=self.facts_table_name,
                query="",
                limit=200
            )
            
            for res in results:
                meta = res.get("metadata", {})
                if meta.get("id") == fact_id:
                    return BusinessFact(
                        id=meta.get("id"),
                        fact=meta.get("fact"),
                        citations=meta.get("citations", []),
                        reason=meta.get("reason", ""),
                        source_agent_id=meta.get("source_agent_id", "system"),
                        created_at=datetime.fromisoformat(meta.get("created_at")) if meta.get("created_at") else datetime.now(timezone.utc),
                        last_verified=datetime.fromisoformat(meta.get("last_verified")) if meta.get("last_verified") else datetime.now(timezone.utc),
                        verification_status=meta.get("verification_status", "unverified"),
                        metadata={"domain": meta.get("domain", "general")}
                    )
            return None
        except Exception as e:
            logger.error(f"Failed to get fact {fact_id}: {e}")
            return None

    async def delete_fact(self, fact_id: str) -> bool:
        """
        Soft delete a fact by marking it as 'deleted'.
        LanceDB is append-only, so we mark rather than remove.
        """
        return await self.update_fact_verification(fact_id, "deleted")


    async def recall_integration_experiences(
        self,
        agent_role: str,
        connector_id: str,
        operation_name: str,
        limit: int = 5
    ) -> List[AgentExperience]:
        """
        Recall past integration execution experiences for learning.

        Args:
            agent_role: Agent category/role
            connector_id: Integration connector
            operation_name: Operation to recall
            limit: Max experiences to return

        Returns:
            List of similar integration experiences
        """
        if self.db.db is None:
            return []

        task_type = f"integration_{connector_id}_{operation_name}"

        # Semantic search for similar experiences
        results = self.db.search(
            table_name=self.table_name,
            query_text=f"Integration {connector_id} {operation_name}",
            limit=limit,
            where={
                "task_type": task_type,
                "agent_role": agent_role
            }
        )

        experiences = []
        for result in results:
            try:
                exp = AgentExperience(
                    id=result.get("id", str(uuid.uuid4())),
                    agent_id=result.get("metadata", {}).get("agent_id", ""),
                    task_type=result.get("metadata", {}).get("task_type", task_type),
                    input_summary=result.get("text", "").split("\n")[1] if "\n" in result.get("text", "") else "",
                    outcome=result.get("metadata", {}).get("outcome", "Unknown"),
                    learnings=result.get("text", "").split("Learnings:")[-1] if "Learnings:" in result.get("text", "") else "",
                    confidence_score=result.get("metadata", {}).get("confidence_score", 0.5),
                    agent_role=agent_role,
                    specialty=result.get("metadata", {}).get("specialty"),
                    timestamp=datetime.fromisoformat(result.get("created_at", datetime.now(timezone.utc).isoformat()))
                )
                experiences.append(exp)
            except Exception as e:
                logger.warning(f"Failed to parse experience: {e}")

        logger.info(
            f"Recalled {len(experiences)} integration experiences for "
            f"{agent_role} on {connector_id}.{operation_name}"
        )

        return experiences

    async def archive_session_to_cold_storage(self, conversation_id: str) -> bool:
        """
        Archive a completed conversation session from Postgres (Hot) to LanceDB (Cold).
        This keeps Postgres small and fast while preserving long-term memory on S3.
        """
        try:
            db = SessionLocal()
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
                "archived_at": datetime.now(timezone.utc).isoformat()
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
                # Soft delete: mark as archived in metadata instead of hard delete
                # This allows recovery if needed and provides audit trail
                try:
                    for msg in messages:
                        # Update metadata to mark as archived
                        msg.metadata_json = msg.metadata_json or {}
                        msg.metadata_json["_archived"] = True
                        msg.metadata_json["_archived_at"] = datetime.now(timezone.utc).isoformat()
                        msg.metadata_json["_archived_to_lancedb"] = True

                    db.commit()
                    logger.info(f"Successfully archived session {conversation_id} to Cold Storage (soft delete)")

                    # ACU Billing Integration
                    try:
                        from core.acu_billing_service import ACUBillingService
                        billing_service = ACUBillingService(db)
                        billing_service.record_system_consumption(
                            tenant_id=self.db.workspace_id,
                            acu_amount=2.0,  # 2 ACUs for session archival
                            task_name=f"archive-session-{conversation_id}"
                        )
                    except Exception as billing_err:
                        logger.warning(f"Failed to record ACU consumption for session archival: {billing_err}")

                except Exception as commit_err:
                    logger.error(f"Failed to mark session as archived: {commit_err}")
                    db.rollback()

            db.close()
            return success
        except Exception as e:
            logger.error(f"Failed to archive session {conversation_id}: {e}")
            return False

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

        db = SessionLocal()
        try:
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
            # (This would be handled by the memory consolidation service)
            result["status"] = "success"
            result["scheduled_for_hard_delete"] = (datetime.now(timezone.utc) + timedelta(days=retention_days)).isoformat()

            logger.info(f"[{audit_id}] ✓ Archival complete. Hard delete scheduled for {result['scheduled_for_hard_delete']}")

            return result

        except Exception as e:
            logger.error(f"[{audit_id}] Failed: {e}")
            result["error"] = str(e)
            db.rollback()
            return result
        finally:
            db.close()

    async def recover_archived_session(self, conversation_id: str) -> dict:
        """
        Recover a soft-deleted session from archival status.
        Removes the archived flags and restores the messages to active state.

        Args:
            conversation_id: Session ID to recover

        Returns:
            Dictionary with recovery status
        """
        result = {
            "conversation_id": conversation_id,
            "status": "failed",
            "recovered_count": 0,
            "error": None
        }

        db = SessionLocal()
        try:
            messages = db.query(ChatMessage).filter(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.tenant_id == self.db.workspace_id,
                ChatMessage.metadata_json.is_not(None),
                ChatMessage.metadata_json.op('?')('_archived')
            ).all()

            if not messages:
                result["error"] = "No archived messages found"
                return result

            # Remove archival flags
            for msg in messages:
                # Keep audit trail but remove archived status
                msg.metadata_json["_recovered"] = True
                msg.metadata_json["_recovered_at"] = datetime.now(timezone.utc).isoformat()
                # Remove the _archived flag
                msg.metadata_json.pop("_archived", None)

            db.commit()
            result["status"] = "success"
            result["recovered_count"] = len(messages)

            logger.info(f"Recovered {len(messages)} messages from session {conversation_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to recover session {conversation_id}: {e}")
            result["error"] = str(e)
            db.rollback()
            return result
        finally:
            db.close()

    async def hard_delete_archived_sessions(self, older_than_days: int = 30) -> dict:
        """
        Permanently delete sessions that have been soft-deleted for longer than the retention period.
        This should be called by the memory consolidation service.

        WARNING: This operation is irreversible! Only use after retention period expires.

        Args:
            older_than_days: Delete sessions archived more than this many days ago

        Returns:
            Dictionary with deletion statistics
        """
        result = {
            "status": "failed",
            "deleted_count": 0,
            "error": None
        }

        db = SessionLocal()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)

            # Find messages that have been archived and are past retention
            messages_to_delete = db.query(ChatMessage).filter(
                ChatMessage.tenant_id == self.db.workspace_id,
                ChatMessage.metadata_json.is_not(None),
                ChatMessage.metadata_json.op('?')('_archived'),
                ChatMessage.metadata_json['_archived'].astext == 'true'
            ).all()

            # Filter by retention date in metadata
            messages_past_retention = []
            for msg in messages_to_delete:
                retention_until = msg.metadata_json.get('_retention_until')
                if retention_until:
                    retention_date = datetime.fromisoformat(retention_until)
                    if retention_date < datetime.now(timezone.utc):
                        messages_past_retention.append(msg)
                elif msg.created_at < cutoff_date:
                    # Fallback: use created_at if retention_until not set
                    messages_past_retention.append(msg)

            if not messages_past_retention:
                result["status"] = "success"
                result["deleted_count"] = 0
                return result

            # Group by conversation_id for logging
            conv_ids = set(m.conversation_id for m in messages_past_retention)

            # Perform hard delete
            for msg in messages_past_retention:
                db.delete(msg)

            db.commit()
            result["status"] = "success"
            result["deleted_count"] = len(messages_past_retention)

            logger.info(f"Hard deleted {len(messages_past_retention)} messages from {len(conv_ids)} sessions")
            return result

        except Exception as e:
            logger.error(f"Failed to hard delete archived sessions: {e}")
            result["error"] = str(e)
            db.rollback()
            return result
        finally:
            db.close()

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
                    db = SessionLocal()
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
                    db.close()
                except Exception as he:
                    logger.warning(f"Hot formula fallback failed: {he}")
        except Exception as fe:
            logger.warning(f"Formula recall failed: {fe}")

        # 4. Search Conversations (Postgres Persistence)
        conversation_results = []
        try:
            db = SessionLocal()
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
            
            db = SessionLocal()
            try:
                episode_service = EpisodeRetrievalService(db)
                episodes_response = await episode_service.retrieve_contextual(
                    agent_id=agent.id,
                    current_task=current_task_description,
                    limit=limit
                )
                episodes_result = episodes_response.get("episodes", [])
                
                # Enrich results with full context if not already enriched by service
                # The service already handles basic serialization, but we can add full context here
                # to match the Upstream "ALWAYS fetch" pattern if needed, 
                # though retrieve_contextual in our service already returns serialized episodes.
                
            finally:
                db.close()

        except Exception as ee:
            logger.warning(f"Episode recall failed: {ee}")

        return {
            "experiences": valid_experiences,
            "knowledge": knowledge_results,
            "knowledge_graph": graph_context,
            "formulas": formula_results,
            "conversations": conversation_results,
            "business_facts": business_facts,
            "episodes": episodes_result
        }

    # ============================================================================
    # Episodic Memory Integration (Phase: Episodic Memory & Graduation)
    # ============================================================================

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

        This wraps the episodic memory system for integration with the World Model.
        Episodes stored in LanceDB are actively queried during agent execution
        for context retrieval based on task similarity.

        Dual Storage:
        - PostgreSQL (hot): Recent episodes for graduation readiness queries
        - LanceDB (active): Full history for semantic search during execution

        Args:
            episode_id: ID of the episode
            agent_id: ID of the agent
            tenant_id: ID of the tenant
            task_description: Description of the task
            outcome: Episode outcome (success/failure/partial)
            learnings: Key insights from this episode
            agent_role: Agent's role/category
            maturity_at_time: Maturity level when episode occurred
            constitutional_score: Constitutional compliance score
            human_intervention_count: Number of human interventions
            confidence_score: Agent's confidence score
            metadata: Additional episode metadata

        Returns:
            True if recorded successfully
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
            table_name="agent_episodes",  # Separate table for episodes
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
        Sync an episode from PostgreSQL to LanceDB for long-term retention and semantic search.
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
        Recall relevant episodes based on task similarity and optional canvas/feedback filtering.

        NEW: Canvas-aware retrieval boosts episodes from the same canvas by +0.3
        and slightly penalizes episodes from different canvases (-0.05).

        NEW: Feedback-aware retrieval boosts episodes with positive feedback (+0.2)
        and penalizes episodes with negative feedback (-0.3). Optional min_feedback_score
        parameter filters out episodes below threshold.

        Agents use this during execution to retrieve relevant past experiences
        from LanceDB. This provides context-aware memory retrieval.

        Args:
            task_description: Current task description
            agent_role: Agent's role/category for filtering
            agent_id: Optional agent ID for more specific recall
            canvas_id: Optional canvas ID for context-aware boosting.
                      Episodes from the same canvas receive relevance boost.
            min_feedback_score: Optional minimum feedback score (-1.0 to 1.0).
                              Only episodes with feedback_score >= this value are returned.
            limit: Maximum number of episodes to return

        Returns:
            List of relevant episodes with enhanced scoring (final_score, canvas_boost, feedback_boost).
        """
        try:
            # Build query with agent role and task description
            query = f"{agent_role} {task_description}"

            results = self.db.search(
                table_name="agent_episodes",
                query=query,
                limit=limit * 2  # Get more results for filtering
            )

            # Filter by agent role and optionally by agent_id
            scored_episodes = []
            for res in results:
                meta = res.get("metadata", {})

                # Filter by agent role
                if meta.get("agent_role") != agent_role:
                    continue

                # Filter by agent_id if specified
                if agent_id and meta.get("agent_id") != agent_id:
                    continue

                # Only include episode types
                if meta.get("type") != "episode":
                    continue

                # Calculate canvas boost (NEW: Canvas-Aware Retrieval)
                base_score = res.get("_score", 0.5)
                canvas_boost = 0.0
                feedback_boost = 0.0

                if canvas_id:
                    episode_canvas_id = meta.get("canvas_id")
                    if episode_canvas_id:
                        if episode_canvas_id == canvas_id:
                            canvas_boost = 0.3  # Same canvas: strong boost
                            logger.debug(f"Boosting episode from same canvas {canvas_id}")
                        else:
                            canvas_boost = -0.05  # Different canvas: small penalty

                # Calculate feedback boost (NEW: Feedback-Aware Retrieval)
                feedback_score = meta.get("feedback_score")
                if feedback_score is not None:
                    if feedback_score > 0.5:
                        feedback_boost = 0.2  # Strong positive feedback: boost
                        logger.debug(f"Boosting episode with positive feedback {feedback_score}")
                    elif feedback_score < -0.5:
                        feedback_boost = -0.3  # Strong negative feedback: penalty
                        logger.debug(f"Penalizing episode with negative feedback {feedback_score}")

                # Apply feedback filter if specified
                if min_feedback_score is not None:
                    if feedback_score is None or feedback_score < min_feedback_score:
                        continue  # Skip episodes below threshold

                final_score = base_score + canvas_boost + feedback_boost

                scored_episodes.append({
                    "episode_id": meta.get("episode_id"),
                    "agent_id": meta.get("agent_id"),
                    "task_description": res.get("text", "").split("Outcome:")[0].replace("Episode: ", "").strip(),
                    "outcome": meta.get("outcome"),
                    "learnings": res.get("text", "").split("Learnings: ")[1].split("\n")[0] if "Learnings:" in res.get("text", "") else "",
                    "maturity_at_time": meta.get("maturity_at_time"),
                    "constitutional_score": meta.get("constitutional_score", 1.0),
                    "human_intervention_count": meta.get("human_intervention_count", 0),
                    "confidence_score": meta.get("confidence_score", 0.5),
                    "canvas_id": meta.get("canvas_id"),  # Canvas metadata
                    "feedback_score": feedback_score,  # For scoring
                    "feedback_id": meta.get("feedback_id"),  # Reference for full retrieval
                    "similarity_score": base_score,
                    "canvas_boost": canvas_boost,
                    "feedback_boost": feedback_boost,  # NEW: Feedback boost amount
                    "final_score": final_score
                })

            # Sort by final_score instead of base_score (NEW)
            scored_episodes.sort(key=lambda x: x["final_score"], reverse=True)

            # Apply limit after sorting
            scored_episodes = scored_episodes[:limit]

            logger.info(
                f"Recalled {len(scored_episodes)} relevant episodes for {agent_role} agent "
                f"(canvas_aware={canvas_id is not None})"
            )
            return scored_episodes

        except Exception as e:
            logger.warning(f"Failed to recall episodes from LanceDB: {e}")
            return []

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
        Recall experiences with configurable detail level

        This is the primary method for agents to retrieve past experiences
        with appropriate context detail for the current reasoning task.

        Args:
            tenant_id: Tenant ID for security
            agent_role: Role/category of agent (e.g., 'Finance', 'Developer')
            task_description: Current task to match against
            detail_level: SUMMARY (50 tokens), STANDARD (200), FULL (500)
            agent_id: Specific agent ID (optional, for more specific recall)
            limit: Maximum experiences to return

        Returns:
            List of experiences with detail appropriate to level
        """
        from core.episode_service import EpisodeService

        episode_service = EpisodeService(self.db)

        # If agent_id specified, recall that agent's episodes
        if agent_id:
            episodes = await episode_service.recall_episodes_with_detail(
                agent_id=agent_id,
                tenant_id=tenant_id,
                detail_level=detail_level,
                limit=limit
            )
            return self._format_episodes_as_experiences(episodes, detail_level)

        # Otherwise, use semantic search via LanceDB (full detail only)
        if detail_level == DetailLevel.FULL:
            # Use existing semantic search for full detail
            experiences = await self.recall_episodes(
                task_description=task_description,
                agent_role=agent_role,
                agent_id=agent_id,
                limit=limit
            )
            return experiences

        # For summary/standard, query PostgreSQL with tenant filter
        from sqlalchemy import text

        query = """
            SELECT
                e.id,
                e.agent_id,
                e.task_description,
                e.metadata_json->>'canvas_type' as canvas_type,
                e.metadata_json->>'presentation_summary' as presentation_summary,
                e.outcome,
                e.success,
                e.constitutional_score,
                e.started_at
        """

        if detail_level == DetailLevel.STANDARD:
            query += """,
                e.metadata_json->>'visual_elements' as visual_elements,
                e.metadata_json->>'critical_data_points' as critical_data_points
        """

        query += """
            FROM agent_episodes e
            JOIN agents a ON e.agent_id = a.id
            WHERE a.tenant_id = :tenant_id
              AND a.category = :agent_role
              AND e.started_at > NOW() - INTERVAL '30 days'
            ORDER BY e.started_at DESC
            LIMIT :limit
        """

        result = await self.db.execute(
            text(query),
            {"tenant_id": tenant_id, "agent_role": agent_role, "limit": limit}
        )

        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]

    def _format_episodes_as_experiences(
        self,
        episodes: List[Dict[str, Any]],
        detail_level: DetailLevel
    ) -> List[Dict[str, Any]]:
        """Format episode records as AgentExperience objects"""
        experiences = []
        for ep in episodes:
            experience = {
                "episode_id": ep.get("id"),
                "task_type": ep.get("task_description", "")[:50],
                "input_summary": ep.get("presentation_summary", ""),
                "outcome": ep.get("outcome"),
                "learnings": [],
                "agent_role": "unknown",
                "detail_level": detail_level.value
            }

            if detail_level == DetailLevel.STANDARD:
                experience["visual_elements"] = ep.get("visual_elements")
                experience["critical_data_points"] = ep.get("critical_data_points")

            if detail_level == DetailLevel.FULL:
                experience["audit_trail"] = ep.get("audit_trail")

            experiences.append(experience)

        return experiences

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

        This is called for episodes older than 30 days to maintain PostgreSQL
        performance while preserving full history in LanceDB.

        Args:
            Same as record_episode()

        Returns:
            True if archived successfully
        """
        try:
            # Sync to LanceDB
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

            if success:
                logger.info(f"Archived episode {episode_id} to LanceDB cold storage")
            else:
                logger.warning(f"Failed to archive episode {episode_id}")

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
        """
        Get recent episodes for graduation readiness calculation.

        Queries PostgreSQL hot storage for recent episodes (fast aggregation).

        Args:
            agent_id: ID of the agent
            tenant_id: ID of the tenant
            limit: Maximum number of episodes to return

        Returns:
            List of recent episodes with metadata
        """
        try:
            from core.database import SessionLocal
            from core.models import AgentEpisode

            db = SessionLocal()
            episodes = db.query(AgentEpisode).filter(
                AgentEpisode.agent_id == agent_id,
                AgentEpisode.tenant_id == tenant_id
            ).order_by(AgentEpisode.started_at.desc()).limit(limit).all()

            result = [
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

            db.close()
            return result

        except Exception as e:
            logger.warning(f"Failed to get recent episodes from PostgreSQL: {e}")
            return []

    def get_episode_feedback_for_decision(
        self,
        episode_ids: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve complete feedback records for multiple episodes.

        Called during agent decision-making to provide full feedback context,
        not just scores stored in metadata.

        Args:
            episode_ids: List of episode IDs to fetch feedback for

        Returns:
            Dictionary mapping episode_id to list of feedback records
        """
        from core.models import EpisodeFeedback

        if not episode_ids:
            return {}

        try:
            db = SessionLocal()
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
                    "provided_at": f.provided_at.isoformat()
                })

            db.close()
            return result

        except Exception as e:
            logger.error(f"Failed to get episode feedback for decision: {e}")
            return {}

    # ============================================================================
    # Skill Recommendation Methods (OpenClaw Integration)
    # ============================================================================

    @dataclass
    class SkillRecommendation:
        """Skill recommendation for a specific task"""
        skill_id: str
        skill_name: Optional[str]
        success_rate: float  # 0.0 to 1.0
        execution_count: int
        last_executed_at: Optional[datetime]
        reason: str  # Human-readable explanation

    def recommend_skills_for_task(
        self,
        task_description: str,
        agent_id: str,
        tenant_id: str,
        limit: int = 5
    ) -> List['WorldModelService.SkillRecommendation']:
        """
        Recommend OpenClaw skills for a task based on past episode outcomes.

        Uses semantic search to find similar past tasks and analyzes which
        OpenClaw skills were used successfully. Ranks skills by:
        1. Success rate (successful executions / total)
        2. Recency (more recent = higher score)
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
            from core.models import AgentEpisode, Skill
            from sqlalchemy import cast

            db = SessionLocal()

            # Step 1: Recall semantically similar episodes using existing method
            # Get agent role for recall (needed for the recall_episodes method)
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id,
                AgentRegistry.tenant_id == tenant_id
            ).first()

            if not agent:
                logger.warning(f"Agent {agent_id} not found for tenant {tenant_id}")
                db.close()
                return []

            agent_role = agent.category or "general"

            # Use async wrapper for recall_episodes
            import asyncio
            try:
                # Try to get event loop, create new one if none exists
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # Recall similar episodes
                similar_episodes = loop.run_until_complete(
                    self.recall_episodes(
                        task_description=task_description,
                        agent_role=agent_role,
                        agent_id=agent_id,
                        limit=limit * 3  # Get more for filtering
                    )
                )
            except Exception as recall_err:
                logger.warning(f"Failed to recall episodes: {recall_err}")
                similar_episodes = []

            # Step 2: Filter for OpenClaw skill episodes and extract skill_ids
            skill_episodes = []
            for ep in similar_episodes:
                metadata = ep.get("metadata", {})
                if metadata.get("skill_type") == "openclaw":
                    skill_id = metadata.get("skill_id")
                    if skill_id:
                        skill_episodes.append({
                            "episode_id": ep.get("episode_id"),
                            "skill_id": skill_id,
                            "outcome": ep.get("outcome"),
                            "similarity_score": ep.get("similarity_score", 0.5),
                            "final_score": ep.get("final_score", ep.get("similarity_score", 0.5))
                        })

            if not skill_episodes:
                logger.info(f"No OpenClaw skill episodes found for task: {task_description[:50]}")
                db.close()
                return []

            # Step 3: Calculate skill statistics from PostgreSQL
            skill_stats = {}
            for ep in skill_episodes:
                skill_id = ep["skill_id"]
                if skill_id not in skill_stats:
                    skill_stats[skill_id] = {
                        "total_executions": 0,
                        "successful_executions": 0,
                        "similarity_scores": [],
                        "last_executed_at": None
                    }

                skill_stats[skill_id]["total_executions"] += 1
                if ep["outcome"] == "success":
                    skill_stats[skill_id]["successful_executions"] += 1
                skill_stats[skill_id]["similarity_scores"].append(ep["final_score"])

            # Step 4: Query PostgreSQL for detailed skill execution stats
            for skill_id in skill_stats.keys():
                # Query all OpenClaw episodes for this skill
                episodes = db.query(AgentEpisode).filter(
                    AgentEpisode.agent_id == agent_id,
                    AgentEpisode.tenant_id == tenant_id,
                    AgentEpisode.metadata_json["skill_type"].astext == "openclaw",
                    AgentEpisode.metadata_json["skill_id"].astext == skill_id
                ).all()

                # Update stats with actual execution counts
                skill_stats[skill_id]["total_executions"] = len(episodes)
                skill_stats[skill_id]["successful_executions"] = sum(1 for e in episodes if e.success)

                # Get last executed time
                if episodes:
                    skill_stats[skill_id]["last_executed_at"] = max(
                        (e.completed_at for e in episodes if e.completed_at),
                        default=None
                    )

            # Step 5: Build recommendations
            recommendations = []
            for skill_id, stats in skill_stats.items():
                # Get skill name from Skill table
                skill = db.query(Skill).filter(Skill.id == skill_id).first()
                skill_name = skill.name if skill else None

                # Calculate success rate
                success_rate = (
                    stats["successful_executions"] / stats["total_executions"]
                    if stats["total_executions"] > 0
                    else 0.0
                )

                # Calculate combined score (success rate + average similarity)
                avg_similarity = sum(stats["similarity_scores"]) / len(stats["similarity_scores"])
                combined_score = (success_rate * 0.6) + (avg_similarity * 0.4)

                recommendations.append(self.SkillRecommendation(
                    skill_id=skill_id,
                    skill_name=skill_name,
                    success_rate=round(success_rate, 4),
                    execution_count=stats["total_executions"],
                    last_executed_at=stats["last_executed_at"],
                    reason=f"Used successfully for similar task (similarity: {avg_similarity:.2f})"
                ))

            db.close()

            # Sort by combined score (success rate weighted more than similarity)
            recommendations.sort(
                key=lambda r: (r.success_rate * 0.6 + 0.4),  # Success rate prioritized
                reverse=True
            )

            # Return top recommendations
            return recommendations[:limit]

        except Exception as e:
            logger.error(f"Failed to recommend skills for task: {e}")
            return []

    def get_successful_skills_for_agent(
        self,
        agent_id: str,
        tenant_id: str,
        limit: int = 100
    ) -> set:
        """
        Get set of skill IDs used successfully by an agent.

        Queries AgentEpisode for OpenClaw skill executions with success=True.
        Results are cached for 5 minutes to improve performance.

        Args:
            agent_id: ID of the agent
            tenant_id: ID of the tenant
            limit: Maximum number of episodes to query

        Returns:
            Set of skill IDs that were executed successfully
        """
        try:
            from core.models import AgentEpisode
            from sqlalchemy import cast

            db = SessionLocal()

            # Query successful OpenClaw skill executions
            episodes = db.query(AgentEpisode).filter(
                AgentEpisode.agent_id == agent_id,
                AgentEpisode.tenant_id == tenant_id,
                AgentEpisode.success == True,
                AgentEpisode.metadata_json["skill_type"].astext == "openclaw"
            ).limit(limit).all()

            # Extract unique skill IDs
            skill_ids = set()
            for ep in episodes:
                if ep.metadata_json:
                    skill_id = ep.metadata_json.get("skill_id")
                    if skill_id:
                        skill_ids.add(skill_id)

            db.close()

            logger.info(f"Found {len(skill_ids)} successful skills for agent {agent_id}")
            return skill_ids

        except Exception as e:
            logger.error(f"Failed to get successful skills for agent: {e}")
            return set()

    # ========================================================================
    # Canvas-Aware Experience Retrieval
    # ========================================================================

    async def recall_experiences_with_canvas(
        self,
        agent_id: str,
        task: str,
        preferred_canvas_type: Optional[str] = None,
        limit: int = 10
    ) -> List[AgentExperience]:
        """
        Recall experiences filtered by successful canvas presentations.

        Enables agents to learn which canvas types work best for specific tasks.
        For example: "User engages longer with line charts than spreadsheets for trends"

        Args:
            agent_id: ID of the agent
            task: Task description for semantic matching
            preferred_canvas_type: Optional canvas type filter (generic, docs, email, sheets, etc.)
            limit: Maximum number of experiences to return

        Returns:
            List of AgentExperience objects with canvas context
        """
        try:
            # Search with task description
            results = self.db.search(
                table_name=self.table_name,
                query=task,
                limit=limit * 2  # Fetch extra for filtering
            )

            experiences = []
            for res in results:
                meta = res.get("metadata", {})

                # Filter by agent_id
                if meta.get("agent_id") != agent_id:
                    continue

                # Filter by preferred canvas type if specified
                if preferred_canvas_type:
                    canvas_types_used = meta.get("canvas_types", [])
                    if preferred_canvas_type not in canvas_types_used:
                        continue

                # Only include successful outcomes
                if meta.get("outcome", "").lower() != "success":
                    continue

                experiences.append(AgentExperience(
                    id=res.get("id", ""),
                    agent_id=meta.get("agent_id", ""),
                    task_type=meta.get("task_type", ""),
                    input_summary=meta.get("input_summary", ""),
                    outcome=meta.get("outcome", ""),
                    learnings=meta.get("learnings", ""),
                    confidence_score=meta.get("confidence_score", 0.5),
                    feedback_score=meta.get("feedback_score"),
                    artifacts=meta.get("artifacts", []),
                    step_efficiency=meta.get("step_efficiency", 1.0),
                    metadata_trace=meta.get("trace", {}),
                    agent_role=meta.get("agent_role", ""),
                    specialty=meta.get("specialty"),
                    timestamp=datetime.fromisoformat(meta.get("timestamp", datetime.now(timezone.utc).isoformat()))
                ))

                if len(experiences) >= limit:
                    break

            logger.info(
                f"Recalled {len(experiences)} canvas-aware experiences for agent {agent_id} "
                f"(preferred: {preferred_canvas_type or 'any'})"
            )
            return experiences

        except Exception as e:
            logger.error(f"Failed to recall canvas-aware experiences: {e}")
            return []

    async def get_canvas_type_preferences(
        self,
        agent_id: str,
        task_type: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze agent's canvas type preferences based on past experiences.

        Returns statistics on which canvas types have been most successful
        for specific task types.

        Args:
            agent_id: ID of the agent
            task_type: Optional task type filter

        Returns:
            Dictionary mapping canvas_type to preference stats:
            {
                "sheets": {
                    "count": 10,
                    "success_rate": 0.8,
                    "avg_engagement": 45.0,
                    "avg_feedback_score": 0.6
                },
                ...
            }
        """
        try:
            # Search for all agent experiences
            query = f"agent_{agent_id}"
            if task_type:
                query += f" {task_type}"

            results = self.db.search(
                table_name=self.table_name,
                query=query,
                limit=500
            )

            # Group by canvas type
            canvas_stats: Dict[str, Dict[str, Any]] = {}

            for res in results:
                meta = res.get("metadata", {})

                # Skip if not this agent
                if meta.get("agent_id") != agent_id:
                    continue

                # Extract canvas types from experience
                canvas_types = meta.get("canvas_types", [])
                outcome = meta.get("outcome", "").lower()
                feedback_score = meta.get("feedback_score", 0.0)
                engagement_time = meta.get("engagement_time_seconds", 0.0)

                for canvas_type in canvas_types:
                    if canvas_type not in canvas_stats:
                        canvas_stats[canvas_type] = {
                            "count": 0,
                            "successes": 0,
                            "total_engagement": 0.0,
                            "total_feedback": 0.0
                        }

                    stats = canvas_stats[canvas_type]
                    stats["count"] += 1

                    if outcome == "success":
                        stats["successes"] += 1

                    stats["total_engagement"] += engagement_time
                    stats["total_feedback"] += feedback_score

            # Calculate averages and success rates
            preferences = {}
            for canvas_type, stats in canvas_stats.items():
                preferences[canvas_type] = {
                    "count": stats["count"],
                    "success_rate": stats["successes"] / stats["count"] if stats["count"] > 0 else 0.0,
                    "avg_engagement": stats["total_engagement"] / stats["count"] if stats["count"] > 0 else 0.0,
                    "avg_feedback_score": stats["total_feedback"] / stats["count"] if stats["count"] > 0 else 0.0
                }

            logger.info(f"Canvas preferences for agent {agent_id}: {list(preferences.keys())}")
            return preferences

        except Exception as e:
            logger.error(f"Failed to get canvas preferences: {e}")
            return {}

    async def recommend_canvas_type(
        self,
        agent_id: str,
        task_type: str,
        task_description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Recommend the best canvas type for a given task based on agent's past experiences.

        Analyzes success rates, user engagement, and feedback to recommend
        the most effective canvas type.

        Args:
            agent_id: ID of the agent
            task_type: Type of task (e.g., "data_analysis", "reporting")
            task_description: Optional detailed task description

        Returns:
            Recommended canvas type with confidence score:
            {
                "canvas_type": "sheets",
                "confidence": 0.85,
                "reason": "High success rate (80%) and positive feedback for this task type",
                "alternatives": ["charts", "markdown"]
            }
        """
        try:
            # Get canvas preferences for this task type
            preferences = await self.get_canvas_type_preferences(agent_id, task_type)

            if not preferences:
                # No preferences found, return generic recommendation
                return {
                    "canvas_type": "generic",
                    "confidence": 0.5,
                    "reason": "No prior experience with this task type",
                    "alternatives": ["sheets", "charts"]
                }

            # Score each canvas type (success rate weighted 60%, feedback 40%)
            scored_canvases = []
            for canvas_type, stats in preferences.items():
                # Require minimum sample size
                if stats["count"] < 3:
                    continue

                score = (
                    stats["success_rate"] * 0.6 +
                    (stats["avg_feedback_score"] + 1.0) / 2.0 * 0.4  # Normalize -1..1 to 0..1
                )

                scored_canvases.append({
                    "canvas_type": canvas_type,
                    "score": score,
                    "stats": stats
                })

            # Sort by score
            scored_canvases.sort(key=lambda x: x["score"], reverse=True)

            if not scored_canvases:
                return {
                    "canvas_type": "generic",
                    "confidence": 0.5,
                    "reason": "Insufficient data for recommendation",
                    "alternatives": list(preferences.keys())[:3]
                }

            # Get top recommendation
            top = scored_canvases[0]
            top_stats = top["stats"]

            reason_parts = []
            if top_stats["success_rate"] > 0.7:
                reason_parts.append(f"High success rate ({top_stats['success_rate']:.0%})")
            if top_stats["avg_feedback_score"] > 0.3:
                reason_parts.append(f"Positive user feedback")
            if top_stats["avg_engagement"] > 30:
                reason_parts.append(f"Strong user engagement ({top_stats['avg_engagement']:.0f}s avg)")

            alternatives = [c["canvas_type"] for c in scored_canvases[1:4]]

            return {
                "canvas_type": top["canvas_type"],
                "confidence": min(0.95, top["score"] + 0.1),  # Boost confidence slightly
                "reason": ", ".join(reason_parts) if reason_parts else "Past performance",
                "alternatives": alternatives
            }

        except Exception as e:
            logger.error(f"Failed to recommend canvas type: {e}")
            return None

    async def record_canvas_outcome(
        self,
        experience: AgentExperience,
        canvas_types_used: List[str],
        engagement_time_seconds: float = 0.0,
        user_feedback: Optional[float] = None
    ) -> bool:
        """
        Record an experience with canvas context for learning.

        Enhances experience recording with canvas type information
        for better future recommendations.

        Args:
            experience: The AgentExperience to record
            canvas_types_used: List of canvas types presented (e.g., ["sheets", "charts"])
            engagement_time_seconds: How long user engaged with the canvas
            user_feedback: Optional user feedback score (-1.0 to 1.0)

        Returns:
            True if recorded successfully
        """
        try:
            # Enhance metadata with canvas context
            enhanced_metadata = experience.metadata or {}
            enhanced_metadata.update({
                "canvas_types": canvas_types_used,
                "engagement_time_seconds": engagement_time_seconds,
                "canvas_count": len(canvas_types_used)
            })

            # If user feedback provided, update feedback_score
            if user_feedback is not None:
                enhanced_metadata["user_feedback"] = user_feedback

            # Create enhanced experience
            enhanced_experience = AgentExperience(
                id=experience.id,
                agent_id=experience.agent_id,
                task_type=experience.task_type,
                input_summary=experience.input_summary,
                outcome=experience.outcome,
                learnings=experience.learnings,
                confidence_score=experience.confidence_score,
                feedback_score=user_feedback if user_feedback is not None else experience.feedback_score,
                artifacts=experience.artifacts,
                step_efficiency=experience.step_efficiency,
                metadata_trace=enhanced_metadata,
                agent_role=experience.agent_role,
                specialty=experience.specialty,
                timestamp=experience.timestamp
            )

            # Record using existing method
            return await self.record_experience(enhanced_experience)

        except Exception as e:
            logger.error(f"Failed to record canvas outcome: {e}")
            return False
