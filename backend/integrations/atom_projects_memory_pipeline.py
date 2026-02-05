"""
ATOM Projects Data Memory Pipeline
Background ingestion for Asana and Jira data into LanceDB for AI/RAG.
"""

import asyncio
from datetime import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

from core.websockets import manager
from integrations.atom_communication_ingestion_pipeline import (
    CommunicationData,
    LanceDBMemoryManager,
    get_memory_manager,
)
from integrations.jira_service import get_jira_service

# from integrations.asana_service import asana_service # Import when ready

logger = logging.getLogger(__name__)

class ProjectsMemoryPipeline:
    """
    Ingests Project data (Tasks, Issues) into the shared LanceDB memory.
    """

    def __init__(self, workspace_id: Optional[str] = None):
        self.memory_manager = get_memory_manager(workspace_id)
        
    async def run_pipeline(self):
        """Main entry point for scheduled ingestion"""
        logger.info("Starting Projects Memory Pipeline...")
        
        await self._ingest_jira()
        # await self._ingest_asana()
        
        logger.info("Projects Memory Pipeline Completed.")

        # Broadcast Status Update
        try:
            await manager.broadcast_event("communication_stats", "status_update", {
                "pipeline": "projects",
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to broadcast projects status: {e}")

    async def _ingest_jira(self):
        """Fetch recent Jira issues and ingest"""
        try:
            logger.info("Fetching Jira Issues for Memory Ingestion...")
            jira = get_jira_service()
            
            # Check connection
            if not jira.test_connection().get("authenticated"):
                 logger.warning("Skipping Jira ingestion: Not Authenticated")
                 return

            # Fetch recent updated issues
            jql = "order by updated DESC"
            results = jira.search_issues(jql=jql, max_results=50)
            issues = results.get("issues", [])
            
            count = 0
            for issue in issues:
                if self._ingest_task("jira", issue):
                    count += 1
            
            logger.info(f"Successfully ingested {count} Jira issues into memory.")
            
        except Exception as e:
            logger.error(f"Jira Ingestion Failed: {e}")

    def _ingest_task(self, source: str, task_data: Dict[str, Any]) -> bool:
        """Map task/issue to CommunicationData structure and ingest"""
        try:
            # Mapping logic specific to Jira
            fields = task_data.get("fields", {})
            summary = fields.get("summary", "Untitled Task")
            description = fields.get("description") or ""
            status = fields.get("status", {}).get("name", "Unknown")
            
            content = f"Task: {summary}\nStatus: {status}\nDescription: {description}\nSource: {source.title()}"
            
            data = CommunicationData(
                id=f"{source}_task_{task_data.get('key')}", # Use Key for Jira
                app_type=f"{source}_task",
                timestamp=datetime.now(), 
                direction="inbound", 
                sender=fields.get("creator", {}).get("displayName", "system"),
                recipient="atom",
                subject=f"Task Update: {summary} ({task_data.get('key')})",
                content=content,
                attachments=[],
                metadata={
                    "task_id": task_data.get('id'),
                    "key": task_data.get('key'),
                    "status": status,
                    "priority": fields.get("priority", {}).get("name"),
                    "raw_data": json.dumps(task_data) # Be careful with size
                },
                status="active", # Active in memory
                priority="normal",
                tags=["project", "task", source],
                vector_embedding=None
            )
            
            return self.memory_manager.ingest_communication(data)
            
        except Exception as e:
            logger.error(f"Error mapping/ingesting task {task_data.get('key')}: {e}")
            return False

# Global Instance
projects_pipeline = ProjectsMemoryPipeline()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(projects_pipeline.run_pipeline())
