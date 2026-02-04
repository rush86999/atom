import logging
from typing import Any, Dict, List

from core.document_learner import DocumentLifecycleLearner
from integrations.microsoft365_service import microsoft365_service
from integrations.onedrive_service import onedrive_service

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

            # Download OneDrive file using Microsoft Graph API
            try:
                import tempfile
                import httpx

                # Download file content from Graph API
                download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
                headers = {"Authorization": f"Bearer {access_token}"}

                async with httpx.AsyncClient() as client:
                    response = await client.get(download_url, headers=headers, timeout=60.0)

                    if response.status_code == 200:
                        # Save to temp file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as f:
                            f.write(response.content)
                            local_path = f.name

                        # Learn from the downloaded file
                        await self.doc_learner.learn_from_file(local_path, workspace_id)

                        # Clean up temp file
                        import os
                        os.unlink(local_path)

                        logger.info(f"Successfully learned from OneDrive file: {file_name}")
                    else:
                        logger.error(f"Failed to download OneDrive file {file_id}: {response.status_code}")
            except Exception as e:
                logger.error(f"Error processing OneDrive file {file_id}: {e}")

    async def scan_outlook_for_lifecycle(self, user_id: str, access_token: str, workspace_id: str):
        """
        Scans Outlook for business lifecycle events (handled by CommunicationIntelligence typically,
        but can be a dedicated historical scan here).
        """
        try:
            import httpx

            # Fetch recent inbox messages via Microsoft Graph API
            messages_url = "https://graph.microsoft.com/v1.0/me/mailfolders/inbox/messages"
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {
                "$top": 50,
                "$select": "subject,from,receivedDateTime,body",
                "$orderby": "receivedDateTime desc"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(messages_url, headers=headers, params=params, timeout=30.0)

                if response.status_code == 200:
                    data = response.json()
                    messages = data.get("value", [])

                    logger.info(f"Scanning {len(messages)} Outlook messages for lifecycle events")

                    # Process messages for lifecycle events
                    for msg in messages:
                        await self._process_outlook_message(msg, user_id, workspace_id)

                else:
                    logger.error(f"Failed to fetch Outlook messages: {response.status_code}")
        except Exception as e:
            logger.error(f"Error scanning Outlook for lifecycle events: {e}")

    async def _process_outlook_message(self, msg: dict, user_id: str, workspace_id: str):
        """Process a single Outlook message for lifecycle events."""
        try:
            subject = msg.get("subject", "")
            from_email = msg.get("from", {}).get("emailAddress", {}).get("address", "")

            # Check for lifecycle event keywords
            lifecycle_keywords = [
                "invoice", "purchase order", "contract", "agreement",
                "proposal", "deal", "closed", "won", "lost",
                "renewal", "subscription", "payment"
            ]

            subject_lower = subject.lower()
            if any(keyword in subject_lower for keyword in lifecycle_keywords):
                logger.info(f"Found potential lifecycle event in message: {subject}")

                # Store in communication intelligence for further processing
                # This would typically be stored in a database or processed by CommunicationIntelligence
                logger.debug(f"Lifecycle event from {from_email}: {subject}")

        except Exception as e:
            logger.error(f"Error processing Outlook message: {e}")
