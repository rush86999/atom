import asyncio
from datetime import datetime
import logging
from typing import Set
from ai.data_intelligence import DataIntelligenceEngine, PlatformType

from core.notification_manager import notification_manager

logger = logging.getLogger(__name__)

class IntelligenceBackgroundWorker:
    """
    Background worker that periodically runs anomaly detection 
    and broadcasts critical insights via WebSockets.
    """
    def __init__(self, interval_seconds: int = 300): # Default 5 mins
        self.engine = DataIntelligenceEngine()
        self.interval = interval_seconds
        self.seen_anomalies: Set[str] = set()
        self.is_running = False
        self._task = None

    async def start(self):
        """Start the background monitoring task"""
        if self.is_running:
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"IntelligenceBackgroundWorker started with interval {self.interval}s")

    async def stop(self):
        """Stop the background task"""
        if not self.is_running:
            return
            
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("IntelligenceBackgroundWorker stopped")

    async def _run_loop(self):
        """Continuous loop for anomaly detection"""
        while self.is_running:
            try:
                await self._perform_scan()
            except Exception as e:
                logger.error(f"Error during intelligence scan: {e}")
            
            await asyncio.sleep(self.interval)

    async def _perform_scan(self):
        """Single scan iteration"""
        # 1. Optionally refresh data if registry is empty
        if not self.engine.entity_registry:
            logger.info("Initializing background engine registry with first-run data")
            for platform in [PlatformType.SALESFORCE, PlatformType.JIRA, PlatformType.ASANA]:
                data = await self.engine._get_platform_data(platform)
                if data:
                    await self.engine.ingest_platform_data(platform, data)

        # 2. Run detection
        anomalies = await self.engine.detect_anomalies()
        
        # 3. Process and broadcast NEW critical anomalies
        for anomaly in anomalies:
            if anomaly.severity == "critical" and anomaly.anomaly_id not in self.seen_anomalies:
                logger.info(f"🚨 New Critical Anomaly Detected: {anomaly.title}")
                
                # Broadcast to the default 'demo-workspace' (or handle per-workspace logic)
                await notification_manager.send_urgent_notification(
                    message=f"CRITICAL RISK: {anomaly.description}",
                    workspace_id="demo-workspace", # Standard for the demo env
                    channel="ui"
                )
                
                self.seen_anomalies.add(anomaly.anomaly_id)
        
        # Cleanup old seen anomalies periodically to allow re-alerting if needed (optional)
        if len(self.seen_anomalies) > 1000:
            self.seen_anomalies.clear()

# Global worker instance
intelligence_worker = IntelligenceBackgroundWorker()
