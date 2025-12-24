import logging
from typing import Dict, Any, List
from integrations.microsoft365_service import microsoft365_service
from integrations.onedrive_service import onedrive_service
from core.document_learner import DocumentLifecycleLearner

logger = logging.getLogger(__name__)

class Microsoft365LifecycleLearner:
    """
    Integrates with Office 365 (OneDrive/Outlook) to learn business lifecycle events.
    """

    def __init__(self, ai_service: Any = None, db_session: Any = None):
        self.doc_learner = DocumentLifecycleLearner(ai_service, db_session)

    async def scan_onedrive_for_lifecycle(self, user_id: str, access_token: str, workspace_id: str):
        """
        Scans OneDrive for business documents and extracts lifecycle events.
        """
        logger.info(f"M365: Starting OneDrive lifecycle scan for user {user_id}")
        
        # 1. Search for relevant keywords
        keywords = ["PO", "Quote", "Invoice", "Shipment", "Order"]
        all_files = []
        
        for kw in keywords:
            files = await onedrive_service.search_files(access_token, kw)
            if files:
                all_files.extend(files)
        
        # Deduplicate by ID
        unique_files = {f["id"]: f for f in all_files if f.get("file")}.values()
        
        logger.info(f"M365: Found {len(unique_files)} potential lifecycle documents.")
        
        for f in unique_files:
            file_id = f["id"]
            file_name = f["name"]
            
            # 2. Download and process
            # Note: In a real app, we'd download to a temp file
            # For this prototype, we'll simulate the download and pass to doc_learner
            logger.info(f"M365: Processing {file_name} ({file_id})")
            
            # Simple simulation: if we had a local path, we'd call doc_learner.learn_from_file
            # In production, this would be: 
            # local_path = await onedrive_service.download_file(access_token, file_id)
            # await self.doc_learner.learn_from_file(local_path, workspace_id)
            pass

    async def scan_outlook_for_lifecycle(self, user_id: str, access_token: str, workspace_id: str):
        """
        Scans Outlook for business lifecycle events (handled by CommunicationIntelligence typically, 
        but can be a dedicated historical scan here).
        """
        # This would use microsoft365_service.get_outlook_messages
        pass
