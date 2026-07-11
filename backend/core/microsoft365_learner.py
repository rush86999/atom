import logging
import re
from typing import Any, Dict, List, Optional

from core.document_learner import DocumentLifecycleLearner
from integrations.microsoft365_service import microsoft365_service
from integrations.onedrive_service import onedrive_service

logger = logging.getLogger(__name__)

# Regexes used to pull structured business data out of email subject/body text.
_TRACKING_RE = re.compile(r"\b(1Z\s?[A-Z0-9]{16}|[A-Z]{2,4}\d{9,}[A-Z]{0,3})\b")
_AMOUNT_RE = re.compile(r"(?:USD|CAD|EUR|\$)\s?([\d,]+\.\d{2})", re.IGNORECASE)
_ORDER_RE = re.compile(r"\b(?:order|PO|invoice|quote)\s*(?:#|no\.?|number)?\s*([A-Z0-9][A-Z0-9\-]{3,})\b", re.IGNORECASE)


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
            result = await onedrive_service.search_files(access_token, kw)
            # search_files returns a {"status","data":{"value":[...]}} envelope.
            files: List[dict] = []
            if isinstance(result, dict):
                if result.get("status") == "success":
                    payload = result.get("data", {})
                    files = payload.get("value", []) if isinstance(payload, dict) else payload
                elif "value" in result:
                    files = result.get("value", [])
            elif isinstance(result, list):
                files = result
            all_files.extend(files)

        # Deduplicate by ID
        unique_files = {f["id"]: f for f in all_files if f.get("file")}.values()

        logger.info(f"M365: Found {len(unique_files)} potential lifecycle documents.")

        for f in unique_files:
            file_id = f["id"]
            file_name = f["name"]

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
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as tmp:
                            tmp.write(response.content)
                            local_path = tmp.name

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
        Scans Outlook for business lifecycle events.

        Detects invoice / purchase order / shipping / payment emails and persists
        the extracted entities (order #, tracking #, vendor, amounts) into the
        knowledge graph so the agent remembers them.
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

                    ingested = 0
                    for msg in messages:
                        if await self._process_outlook_message(msg, user_id, workspace_id):
                            ingested += 1
                    logger.info(f"Outlook lifecycle scan ingested {ingested} entity-bearing messages")
                else:
                    logger.error(f"Failed to fetch Outlook messages: {response.status_code}")
        except Exception as e:
            logger.error(f"Error scanning Outlook for lifecycle events: {e}")

    async def _process_outlook_message(self, msg: dict, user_id: str, workspace_id: str) -> bool:
        """Process a single Outlook message, persisting detected lifecycle entities.

        Returns True if any entities were extracted and ingested.
        """
        try:
            subject = msg.get("subject", "")
            from_email = msg.get("from", {}).get("emailAddress", {}).get("address", "")
            from_name = msg.get("from", {}).get("emailAddress", {}).get("name", "")
            received = msg.get("receivedDateTime", "")
            body = msg.get("body", {})
            if isinstance(body, dict):
                body_text = body.get("content", "")
            else:
                body_text = str(body)

            haystack = f"{subject}\n{body_text}"

            # Check for lifecycle event keywords
            lifecycle_keywords = [
                "invoice", "purchase order", "contract", "agreement",
                "proposal", "deal", "closed", "won", "lost",
                "renewal", "subscription", "payment", "shipped", "tracking",
                "order confirmation", "quote",
            ]

            subject_lower = subject.lower()
            haystack_lower = haystack.lower()
            matched = [kw for kw in lifecycle_keywords if kw in haystack_lower]
            if not matched:
                return False

            logger.info(f"Found lifecycle event in message: {subject}")

            # Extract structured data
            order_ids = _ORDER_RE.findall(haystack)
            tracking_ids = _TRACKING_RE.findall(haystack)
            amounts = _AMOUNT_RE.findall(haystack)

            entities, relationships = self._build_entities(
                subject=subject,
                from_email=from_email,
                from_name=from_name,
                received=received,
                matched_keywords=matched,
                order_ids=order_ids,
                tracking_ids=tracking_ids,
                amounts=amounts,
                body_preview=haystack[:500],
                message_id=msg.get("id"),
            )

            if not entities:
                return False

            return await self._persist_to_graph(workspace_id, entities, relationships)

        except Exception as e:
            logger.error(f"Error processing Outlook message: {e}")
            return False

    def _build_entities(
        self,
        subject: str,
        from_email: str,
        from_name: str,
        received: str,
        matched_keywords: List[str],
        order_ids: List[str],
        tracking_ids: List[str],
        amounts: List[str],
        body_preview: str,
        message_id: Optional[str],
    ) -> tuple[list, list]:
        """Build knowledge-graph entities and relationships from extracted data."""
        entities: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []

        # Sender (vendor/contact) entity
        sender_id = f"contact:{from_email or from_name}"
        if from_email or from_name:
            entities.append({
                "id": sender_id,
                "type": "contact",
                "name": from_name or from_email,
                "properties": {"email": from_email, "name": from_name, "source": "outlook"},
            })

        # The email / lifecycle event itself
        event_id = f"email:{message_id or received or subject}"
        entities.append({
            "id": event_id,
            "type": "email",
            "name": subject or "(no subject)",
            "properties": {
                "subject": subject,
                "from": from_email,
                "received": received,
                "keywords": matched_keywords,
                "preview": body_preview,
                "source": "outlook",
            },
        })
        if from_email or from_name:
            relationships.append({
                "source": sender_id,
                "target": event_id,
                "type": "sent",
            })

        # Order / PO / invoice entities
        for oid in order_ids[:5]:
            oid_norm = oid.strip().upper()
            ent_id = f"order:{oid_norm}"
            entities.append({
                "id": ent_id,
                "type": "order",
                "name": oid_norm,
                "properties": {"order_id": oid_norm, "source": "outlook"},
            })
            relationships.append({"source": event_id, "target": ent_id, "type": "references"})

        # Shipment / tracking entities
        for tid in tracking_ids[:5]:
            tid_norm = tid.strip()
            ent_id = f"shipment:{tid_norm}"
            entities.append({
                "id": ent_id,
                "type": "shipment",
                "name": tid_norm,
                "properties": {"tracking_number": tid_norm, "source": "outlook"},
            })
            relationships.append({"source": event_id, "target": ent_id, "type": "references"})

        # Monetary amounts (stored as properties on the event, not separate entities)
        if amounts:
            entities = [
                {**e, "properties": {**e.get("properties", {}), "amounts": amounts[:5]}}
                if e["id"] == event_id else e
                for e in entities
            ]

        return entities, relationships

    async def _persist_to_graph(
        self, workspace_id: str, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]
    ) -> bool:
        """Write entities/relationships into the GraphRAG knowledge graph."""
        try:
            from core.graphrag_engine import GraphRAGEngine

            engine = GraphRAGEngine()
            engine.ingest_structured_data(
                workspace_id=workspace_id, entities=entities, relationships=relationships
            )
            logger.info(
                f"Ingested {len(entities)} entities / {len(relationships)} relationships from Outlook"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to persist Outlook entities to knowledge graph: {e}")
            return False

