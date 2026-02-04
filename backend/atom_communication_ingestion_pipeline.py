"""
ATOM Communication Ingestion Pipeline
Handles real-time ingestion of messages from various communication platforms
"""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageSource(Enum):
    SLACK = "slack"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    TEAMS = "teams"
    EMAIL = "email"

@dataclass
class NormalizedMessage:
    """Standardized message format across all platforms"""
    source: str
    source_id: str
    content: str
    sender_id: str
    sender_name: str
    timestamp: str
    metadata: Dict[str, Any]
    priority: str = "normal"
    processed: bool = False

class CommunicationIngestionPipeline:
    """
    Real-time ingestion pipeline for communication data
    Normalizes and processes messages from multiple sources
    """
    
    def __init__(self):
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        self.processed_count = 0
        self.error_count = 0
        self.active_sources = set()
        # Default configuration: all enabled by default
        self.integration_settings = {
            MessageSource.SLACK.value: True,
            MessageSource.DISCORD.value: True,
            MessageSource.WHATSAPP.value: True,
            MessageSource.TEAMS.value: True,
            MessageSource.EMAIL.value: True
        }
        
    async def start(self):
        """Start the ingestion pipeline"""
        self.is_running = True
        logger.info("Communication Ingestion Pipeline started")
        asyncio.create_task(self._process_queue())
        
    async def stop(self):
        """Stop the ingestion pipeline"""
        self.is_running = False
        logger.info("Communication Ingestion Pipeline stopped")

    def update_integration_settings(self, source: str, enabled: bool) -> bool:
        """
        Update settings for a specific integration
        Returns True if successful, False if source unknown
        """
        if source in self.integration_settings:
            self.integration_settings[source] = enabled
            status = "enabled" if enabled else "disabled"
            logger.info(f"Integration {source} {status}")
            return True
        return False

    def get_integration_settings(self) -> Dict[str, bool]:
        """Get current integration settings"""
        return self.integration_settings.copy()
        
    async def ingest_message(self, source: str, raw_data: Dict[str, Any]) -> bool:
        """
        Ingest a raw message from a specific source
        Returns True if successfully queued
        """
        # Check if integration is enabled
        if not self.integration_settings.get(source, False):
            logger.warning(f"Ignored message from disabled source: {source}")
            return False

        try:
            normalized = self._normalize_message(source, raw_data)
            if normalized:
                await self.message_queue.put(normalized)
                self.active_sources.add(source)
                logger.debug(f"Queued message from {source}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error ingesting message from {source}: {str(e)}")
            self.error_count += 1
            return False
            
    def _normalize_message(self, source: str, data: Dict[str, Any]) -> Optional[NormalizedMessage]:
        """Normalize raw data into standard format"""
        try:
            timestamp = datetime.now().isoformat()
            
            if source == MessageSource.SLACK.value:
                return NormalizedMessage(
                    source=source,
                    source_id=data.get("event_id", ""),
                    content=data.get("text", ""),
                    sender_id=data.get("user", ""),
                    sender_name=data.get("username", "Unknown"),
                    timestamp=data.get("ts", timestamp),
                    metadata={"channel": data.get("channel")}
                )
                
            elif source == MessageSource.DISCORD.value:
                return NormalizedMessage(
                    source=source,
                    source_id=data.get("id", ""),
                    content=data.get("content", ""),
                    sender_id=data.get("author", {}).get("id", ""),
                    sender_name=data.get("author", {}).get("username", "Unknown"),
                    timestamp=data.get("timestamp", timestamp),
                    metadata={"guild_id": data.get("guild_id")}
                )
                
            elif source == MessageSource.WHATSAPP.value:
                return NormalizedMessage(
                    source=source,
                    source_id=data.get("id", ""),
                    content=data.get("text", {}).get("body", ""),
                    sender_id=data.get("from", ""),
                    sender_name=data.get("profile", {}).get("name", "Unknown"),
                    timestamp=data.get("timestamp", timestamp),
                    metadata={"type": data.get("type")}
                )
                
            else:
                # Generic fallback
                return NormalizedMessage(
                    source=source,
                    source_id=data.get("id", str(time.time())),
                    content=data.get("content", str(data)),
                    sender_id=data.get("sender", "unknown"),
                    sender_name=data.get("sender_name", "Unknown"),
                    timestamp=timestamp,
                    metadata=data
                )
                
        except Exception as e:
            logger.error(f"Normalization error for {source}: {str(e)}")
            return None

    async def _process_queue(self):
        """Process messages from the queue"""
        while self.is_running:
            try:
                if self.message_queue.empty():
                    await asyncio.sleep(0.1)
                    continue
                    
                message: NormalizedMessage = await self.message_queue.get()
                
                # Simulate processing (e.g., AI analysis, storage, routing)
                await self._handle_message(message)
                
                self.processed_count += 1
                self.message_queue.task_done()
                
            except Exception as e:
                logger.error(f"Queue processing error: {str(e)}")
                await asyncio.sleep(1)

    async def _handle_message(self, message: NormalizedMessage):
        """Handle a normalized message"""
        # This is where actual business logic would go
        # e.g., Store in DB, Trigger AI Workflow, Send Notification
        logger.info(f"Processing {message.source} message from {message.sender_name}: {message.content[:50]}...")
        
        # Simulate processing time
        await asyncio.sleep(0.01)
        message.processed = True

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        return {
            "status": "running" if self.is_running else "stopped",
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "queue_size": self.message_queue.qsize(),
            "active_sources": list(self.active_sources)
        }

# Global pipeline instance
ingestion_pipeline = CommunicationIngestionPipeline()

async def main():
    """Test the pipeline"""
    pipeline = CommunicationIngestionPipeline()
    await pipeline.start()
    
    # Simulate incoming messages
    test_messages = [
        ("slack", {"text": "Hello team!", "user": "U123", "username": "alice"}),
        ("discord", {"content": "Build failed", "author": {"id": "D456", "username": "bob"}}),
        ("whatsapp", {"text": {"body": "Meeting confirmed"}, "from": "15551234567"})
    ]
    
    for source, data in test_messages:
        await pipeline.ingest_message(source, data)
        
    await asyncio.sleep(1)
    print(json.dumps(pipeline.get_stats(), indent=2))
    await pipeline.stop()

if __name__ == "__main__":
    asyncio.run(main())
