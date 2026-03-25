"""
Memory Consolidation Service for Upstream

Automatically consolidates and archives agent memories from PostgreSQL (Hot) to LanceDB (Cold).
Maintains optimal database performance and memory lifecycle.
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from core.database import SessionLocal
from core.models import (
    AgentMemory, ChatMessage, AgentRegistry, Tenant
)
from core.lancedb_handler import get_lancedb_handler

logger = logging.getLogger(__name__)

class MemoryConsolidationService:
    """
    Service for automatic memory consolidation and archival.
    Adapted for Upstream with multi-tenant support.
    """

    # Lifecycle thresholds (in days)
    HOT_DAYS = 7          # Keep recent memories in PostgreSQL
    WARM_DAYS = 30        # Transition period
    COLD_DAYS = 90        # Delete low-importance memories after this
    IMPORTANCE_THRESHOLD = 0.3  # Delete memories below this score

    def __init__(self):
        self.consolidation_stats = {
            "sessions_archived": 0,
            "memories_archived": 0,
            "memories_deleted": 0,
            "errors": [],
            "last_run": None
        }

    async def consolidate_all_memories(self) -> Dict[str, Any]:
        """
        Consolidate memories for the system.
        Since Upstream is single-tenant, we consolidate the 'default' workspace.
        """
        logger.info("Starting memory consolidation")
        start_time = datetime.now()
        
        try:
            # For open-source, we focus on the single 'default' tenant
            tenant_id = "default"
            stats = await self.consolidate_tenant(tenant_id)
            
            duration = (datetime.now() - start_time).total_seconds()
            stats["duration_seconds"] = duration
            stats["last_run"] = datetime.now().isoformat()
            
            logger.info(f"Consolidation completed: {stats}")
            return stats

        except Exception as e:
            error_msg = f"Consolidation failed: {str(e)}"
            logger.error(error_msg)
            return {"status": "error", "error": error_msg}

    async def consolidate_tenant(self, tenant_id: str) -> Dict[str, Any]:
        """
        Consolidate memories for a specific tenant.
        """
        memories_archived = 0
        memories_deleted = 0
        errors: List[str] = []

        try:
            # 1. Archive old agent memories
            memories_archived = await self._archive_old_memories(tenant_id)

            # 2. Delete forgotten (low-importance) memories
            memories_deleted = await self._delete_forgotten_memories(tenant_id)

            logger.info(f"Tenant {tenant_id} consolidation: {memories_archived} archived, {memories_deleted} deleted")

        except Exception as e:
            error_msg = f"Tenant consolidation error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        return {
            "tenant_id": tenant_id,
            "memories_archived": memories_archived,
            "memories_deleted": memories_deleted,
            "errors": errors
        }

    async def _archive_old_memories(self, tenant_id: str) -> int:
        """
        Archive agent memories older than HOT_DAYS to LanceDB.
        Transitions them from Hot (PostgreSQL) to Cold (LanceDB).
        """
        count: int = 0
        db = SessionLocal()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.HOT_DAYS)

            # Get old memories that haven't been archived
            query = db.query(AgentMemory).filter(
                AgentMemory.tenant_id == tenant_id,
                AgentMemory.created_at < cutoff_date
            )
            
            # Use extra check for archival
            old_memories = [m for m in query.all() if not (m.metadata_json or {}).get("_archived")]

            if not old_memories:
                return 0

            logger.info(f"Found {len(old_memories)} old memories for tenant {tenant_id}")

            # Archive to LanceDB
            lancedb = get_lancedb_handler(tenant_id)

            for memory in old_memories:
                try:
                    # Create archival document
                    metadata = {
                        "agent_id": memory.agent_id,
                        "memory_type": memory.memory_type,
                        "importance_score": memory.importance_score,
                        "access_count": memory.access_count,
                        "original_id": memory.id,
                        "type": "archived_memory",
                        "archived_at": datetime.now(timezone.utc).isoformat()
                    }

                    success = lancedb.add_document(
                        table_name="archived_memories",
                        text=memory.content,
                        source=f"agent_memory:{memory.agent_id}",
                        metadata=metadata
                    )

                    if success:
                        # Mark as archived (soft delete logic)
                        meta = memory.metadata_json or {}
                        meta["_archived"] = "true"
                        meta["_archived_at"] = datetime.now(timezone.utc).isoformat()
                        memory.metadata_json = meta
                        db.commit()
                        count += 1

                except Exception as e:
                    logger.error(f"Failed to archive memory {memory.id}: {e}")
                    db.rollback()

            logger.info(f"Archived {count} memories for tenant {tenant_id}")
            return count

        except Exception as e:
            logger.error(f"Memory archival failed for tenant {tenant_id}: {e}")
            return 0
        finally:
            db.close()

    async def _delete_forgotten_memories(self, tenant_id: str) -> int:
        """
        Delete low-importance memories older than COLD_DAYS.
        """
        count = 0
        db = SessionLocal()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.COLD_DAYS)

            # Find forgotten memories (already archived, low importance, and old)
            forgotten_memories = db.query(AgentMemory).filter(
                and_(
                    AgentMemory.tenant_id == tenant_id,
                    AgentMemory.created_at < cutoff_date,
                    AgentMemory.importance_score < self.IMPORTANCE_THRESHOLD,
                    AgentMemory.metadata_json.is_not(None),
                    AgentMemory.metadata_json.has_key('_archived')
                )
            ).all()

            for memory in forgotten_memories:
                try:
                    logger.info(f"Deleting forgotten memory {memory.id} (importance: {memory.importance_score})")
                    db.delete(memory)
                    db.commit()
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to delete memory {memory.id}: {e}")
                    db.rollback()

            return count
        except Exception as e:
            logger.error(f"Memory deletion failed for tenant {tenant_id}: {e}")
            return 0
        finally:
            db.close()

    def update_importance_scores(self, tenant_id: str) -> int:
        """
        Update memory importance scores based on access patterns.
        """
        db = SessionLocal()
        try:
            memories = db.query(AgentMemory).filter(
                AgentMemory.tenant_id == tenant_id
            ).all()

            updated = 0
            now = datetime.now(timezone.utc)
            for memory in memories:
                new_score = 0.5 # Base score
                
                # Access count boost (diminishing returns)
                access_boost = min(0.3, memory.access_count * 0.01)
                new_score += access_boost

                # Recency boost
                if memory.last_accessed_at:
                    days_since_access = (now - memory.last_accessed_at.replace(tzinfo=timezone.utc)).days
                    if days_since_access < 7:
                        new_score += 0.2
                    elif days_since_access < 30:
                        new_score += 0.1

                # Clamp to [0, 1]
                new_score = max(0.0, min(1.0, new_score))

                if abs(new_score - (memory.importance_score or 0.5)) > 0.05:
                    memory.importance_score = new_score
                    updated += 1

            db.commit()
            return updated
        except Exception as e:
            logger.error(f"Failed to update importance scores: {e}")
            return 0
        finally:
            db.close()

# Global service instance
memory_consolidation_service = MemoryConsolidationService()

def get_memory_consolidation_service() -> MemoryConsolidationService:
    return memory_consolidation_service
