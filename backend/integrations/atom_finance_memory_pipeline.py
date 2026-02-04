"""
ATOM Finance Data Memory Pipeline
Background ingestion for Stripe and Xero data into LanceDB for AI/RAG.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.websockets import manager
from integrations.atom_communication_ingestion_pipeline import (
    CommunicationData,
    LanceDBMemoryManager,
    get_memory_manager,
)
from integrations.stripe_service import stripe_service

logger = logging.getLogger(__name__)

class FinanceMemoryPipeline:
    """
    Ingests Finance data (Transactions, Invoices) into the shared LanceDB memory.
    """

    def __init__(self, workspace_id: Optional[str] = None):
        self.memory_manager = get_memory_manager(workspace_id)
        
    async def run_pipeline(self):
        """Main entry point for scheduled ingestion"""
        logger.info("Starting Finance Memory Pipeline...")
        
        await self._ingest_stripe()
        # await self._ingest_xero()
        
        logger.info("Finance Memory Pipeline Completed.")

        # Broadcast Status Update
        try:
            await manager.broadcast_event("communication_stats", "status_update", {
                "pipeline": "finance",
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to broadcast finance status: {e}")

    async def _ingest_stripe(self):
        """Fetch recent Stripe charges and ingest"""
        try:
            logger.info("Fetching Stripe Transactions for Memory Ingestion...")
            
            token = os.getenv("STRIPE_SECRET_KEY")
            if not token:
                logger.warning("Skipping Stripe ingestion: No Secret Key")
                return

            # Fetch recent charges
            response = stripe_service.list_payments(token, limit=50)
            charges = response.get("data", [])
            
            count = 0
            for charge in charges:
                if self._ingest_transaction("stripe", charge):
                    count += 1
            
            logger.info(f"Successfully ingested {count} Stripe transactions into memory.")
            
        except Exception as e:
            logger.error(f"Stripe Ingestion Failed: {e}")

    def _ingest_transaction(self, source: str, tx_data: Dict[str, Any]) -> bool:
        """Map transaction to CommunicationData structure and ingest"""
        try:
            amount = float(tx_data.get("amount", 0)) / 100.0
            currency = tx_data.get("currency", "usd")
            desc = tx_data.get("description") or "No Description"
            status = tx_data.get("status")
            
            content = f"Transaction: {desc}\nAmount: {amount} {currency.upper()}\nStatus: {status}\nSource: {source.title()}"
            
            data = CommunicationData(
                id=f"{source}_tx_{tx_data.get('id')}",
                app_type=f"{source}_transaction",
                timestamp=datetime.fromtimestamp(tx_data.get("created", 0)), 
                direction="inbound", 
                sender="system",
                recipient="atom",
                subject=f"Finance Update: {desc}",
                content=content,
                attachments=[],
                metadata={
                    "tx_id": tx_data.get('id'),
                    "amount": amount,
                    "currency": currency,
                    "status": status,
                    "raw_data": json.dumps(tx_data)
                },
                status="active",
                priority="normal",
                tags=["finance", "transaction", source],
                vector_embedding=None
            )
            
            return self.memory_manager.ingest_communication(data)
            
        except Exception as e:
            logger.error(f"Error mapping/ingesting transaction {tx_data.get('id')}: {e}")
            return False

# Global Instance
finance_pipeline = FinanceMemoryPipeline()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(finance_pipeline.run_pipeline())
