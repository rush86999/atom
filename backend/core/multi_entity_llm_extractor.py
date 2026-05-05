"""
Multi-Entity LLM Extraction Service

Extracts multiple entities from unstructured data (emails, messages) using LLM.
Key Innovation: Each extracted entity has _discovered_type field for schema discovery.

Phase 323: Multi-Entity Extraction Enhancement
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from core.llm_service import LLMService
from core.models import DiscoveredEntity

logger = logging.getLogger(__name__)


class MultiEntityLLMExtractor:
    """
    Extract multiple entities from unstructured text using LLM.

    Features:
    - Extract 2-3 entities per email/message
    - Assign _discovered_type to each entity (PascalCase)
    - Calculate confidence scores (0.0 to 1.0)
    - Support batch processing for efficiency

    Performance Targets:
    - Extraction speed: 3-5s per email
    - Cost: $0.007 per email (with optimizations)
    - Accuracy: 85%+ correct entity types
    """

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        model: str = "gpt-4o"  # Cost-effective, fast
    ):
        """
        Initialize Multi-Entity LLM Extractor.

        Args:
            llm_service: LLM service instance (uses default if not provided)
            model: LLM model to use (gpt-4o, gpt-4o-mini, etc.)
        """
        self.llm = llm_service or LLMService()
        self.model = model

    async def extract_from_email(
        self,
        email_data: Dict[str, Any],
        tenant_id: str,
        workspace_id: str,
        batch_id: Optional[str] = None
    ) -> List[DiscoveredEntity]:
        """
        Extract multiple entities from an email.

        Args:
            email_data: Normalized email dict with subject, from, to, body
                Example:
                {
                    "id": "email-001",
                    "subject": "Purchase Order PO-12345 Approved",
                    "from": "vendor@acme.com",
                    "to": ["admin@company.com"],
                    "body": "Please approve PO-12345 for $5,000."
                }
            tenant_id: Tenant UUID
            workspace_id: Workspace UUID
            batch_id: Optional batch ID for grouping

        Returns:
            List of DiscoveredEntity instances (2-3 per email)
        """
        # Build extraction prompt
        prompt = self._build_extraction_prompt(email_data)

        try:
            # Call LLM
            llm_response = await self._call_llm(prompt)

            # Parse response
            extracted_entities = self._parse_llm_response(
                llm_response,
                source_record_id=email_data["id"],
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                batch_id=batch_id
            )

            logger.info(f"Extracted {len(extracted_entities)} entities from {email_data.get('id')}")
            return extracted_entities

        except Exception as e:
            logger.error(f"Failed to extract entities from email {email_data.get('id')}: {e}")
            return []

    def _build_extraction_prompt(self, email_data: Dict[str, Any]) -> str:
        """
        Build LLM prompt for entity extraction.

        Args:
            email_data: Normalized email data

        Returns:
            Extraction prompt with few-shot examples
        """
        # Truncate body to stay within token limits
        body = email_data.get('body', '')[:3000]

        prompt = f"""Analyze this email and extract ALL business entities mentioned.

Email Subject: {email_data.get('subject', '')}
From: {email_data.get('from', '')}
To: {email_data.get('to', '')}
Body:
{body}

Extract entities in JSON format:
{{
    "entities": [
        {{
            "type": "PurchaseOrder",  // PascalCase entity type
            "properties": {{
                "po_number": "PO-12345",
                "vendor": "Acme Corp",
                "amount": 5000.00,
                "currency": "USD",
                "approval_status": "pending"
            }},
            "confidence": 0.95
        }},
        {{
            "type": "SecurityEvent",
            "properties": {{
                "event_type": "unusual_login",
                "severity": "high",
                "user": "john@example.com",
                "location": "Unknown IP",
                "detected_at": "2026-05-05T10:30:00Z"
            }},
            "confidence": 0.88
        }}
    ]
}}

Rules:
1. Extract 2-5 entities per email (prioritize business-critical entities)
2. Use PascalCase for entity types (PurchaseOrder, Invoice, Ticket, Lead, SecurityEvent, Product, etc.)
3. Include ALL relevant properties for each entity
4. Assign confidence scores (0.0 to 1.0) based on extraction certainty
5. Skip generic entities like "Person" or "Organization" (focus on business entities)
6. If no entities found, return empty array: {{"entities": []}}

Return ONLY valid JSON. No markdown, no code blocks.
"""
        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """
        Call LLM service with extraction prompt.

        Args:
            prompt: Extraction prompt

        Returns:
            LLM response text
        """
        # TODO: Implement actual LLM call
        # For now, return mock response
        return '''
{
    "entities": [
        {
            "type": "PurchaseOrder",
            "properties": {
                "po_number": "PO-12345",
                "vendor": "Acme Corp",
                "amount": 5000.0,
                "currency": "USD"
            },
            "confidence": 0.95
        }
    ]
}
'''

    def _parse_llm_response(
        self,
        llm_response: str,
        source_record_id: str,
        tenant_id: str,
        workspace_id: str,
        batch_id: Optional[str] = None
    ) -> List[DiscoveredEntity]:
        """
        Parse LLM JSON response into DiscoveredEntity instances.

        Args:
            llm_response: LLM response text (JSON)
            source_record_id: Source email/message ID
            tenant_id: Tenant UUID
            workspace_id: Workspace UUID
            batch_id: Optional batch ID for grouping

        Returns:
            List of DiscoveredEntity instances
        """
        try:
            # Clean response (remove markdown code blocks if present)
            cleaned_response = llm_response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            # Parse JSON
            response_data = json.loads(cleaned_response)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response content: {llm_response[:500]}")
            return []

        # Create DiscoveredEntity instances
        entities = []
        for entity_data in response_data.get("entities", []):
            try:
                discovered_entity = DiscoveredEntity(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    _discovered_type=entity_data["type"],  # ✅ KEY INNOVATION
                    properties=entity_data["properties"],
                    confidence_score=entity_data.get("confidence", 0.7),
                    source_record_id=source_record_id,
                    source_record_type="email",
                    extraction_metadata={
                        "llm_model": self.model,
                        "batch_id": batch_id,
                        "extracted_at": datetime.now(timezone.utc).isoformat()
                    }
                )
                entities.append(discovered_entity)

            except Exception as e:
                logger.error(f"Failed to create DiscoveredEntity: {e}")
                logger.debug(f"Entity data: {entity_data}")
                continue

        return entities

    async def extract_batch(
        self,
        emails: List[Dict[str, Any]],
        tenant_id: str,
        workspace_id: str,
        batch_id: Optional[str] = None
    ) -> List[DiscoveredEntity]:
        """
        Extract entities from a batch of emails.

        Args:
            emails: List of normalized email dicts
            tenant_id: Tenant UUID
            workspace_id: Workspace UUID
            batch_id: Optional batch ID for grouping

        Returns:
            List of all extracted entities from all emails

        Note: TODO: Implement true batch processing in Plan 323-03
        Current implementation processes sequentially
        """
        all_entities = []

        for email in emails:
            entities = await self.extract_from_email(
                email,
                tenant_id,
                workspace_id,
                batch_id=batch_id
            )
            all_entities.extend(entities)

        logger.info(f"Batch extraction complete: {len(all_entities)} entities from {len(emails)} emails")
        return all_entities
