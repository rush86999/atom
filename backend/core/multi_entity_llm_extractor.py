"""
Multi-Entity LLM Extraction Service

Extracts multiple entities from unstructured data (emails, messages) using LLM.
Key Innovation: Each extracted entity has _discovered_type field for schema discovery.

Phase 323: Multi-Entity Extraction Enhancement
"""

import logging
import json
import asyncio
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from collections import defaultdict

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
        model: str = "gpt-4o",  # Cost-effective, fast
        enable_prompt_caching: bool = True,
        enable_model_selection: bool = True
    ):
        """
        Initialize Multi-Entity LLM Extractor.

        Args:
            llm_service: LLM service instance (uses default if not provided)
            model: LLM model to use (gpt-4o, gpt-4o-mini, etc.)
            enable_prompt_caching: Enable prompt caching for similar emails
            enable_model_selection: Enable intelligent model selection
        """
        self.llm = llm_service or LLMService()
        self.model = model
        self.enable_prompt_caching = enable_prompt_caching
        self.enable_model_selection = enable_model_selection

        # Prompt cache: category -> prompt template
        self.prompt_cache: Dict[str, str] = {}

        # Cache statistics
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "total": 0
        }

        # Model selection statistics
        self.model_stats = {
            "gpt-4o": 0,
            "gpt-4o-mini": 0,
            "total": 0
        }

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
        # Select model based on complexity
        selected_model = self._select_model(email_data)

        # Build extraction prompt
        prompt = self._build_extraction_prompt(email_data)

        try:
            # Call LLM with selected model
            llm_response = await self._call_llm(prompt, model=selected_model)

            # Parse response
            extracted_entities = self._parse_llm_response(
                llm_response,
                source_record_id=email_data["id"],
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                batch_id=batch_id
            )

            logger.info(f"Extracted {len(extracted_entities)} entities from {email_data.get('id')} using {selected_model}")
            return extracted_entities

        except Exception as e:
            logger.error(f"Failed to extract entities from email {email_data.get('id')}: {e}")
            return []

    def _build_extraction_prompt(self, email_data: Dict[str, Any]) -> str:
        """
        Build LLM prompt for entity extraction with caching support.

        Args:
            email_data: Normalized email data

        Returns:
            Extraction prompt with few-shot examples
        """
        # Check cache first
        if self.enable_prompt_caching:
            cached_prompt = self._get_cached_prompt(email_data)
            if cached_prompt:
                self.cache_stats["hits"] += 1
                self.cache_stats["total"] += 1
                logger.debug(f"Prompt cache hit (hit rate: {self._get_cache_hit_rate():.1%})")
                return cached_prompt

        # Cache miss - build prompt
        self.cache_stats["misses"] += 1
        self.cache_stats["total"] += 1

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

        # Cache the prompt
        if self.enable_prompt_caching:
            self._cache_prompt(email_data, prompt)

        return prompt

    async def _call_llm(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Call LLM service with extraction prompt.

        Args:
            prompt: Extraction prompt
            model: LLM model to use (defaults to instance model)

        Returns:
            LLM response text
        """
        # Use specified model or default
        llm_model = model or self.model

        # TODO: Implement actual LLM call
        # For now, return mock response
        return f'''
{{
    "entities": [
        {{
            "type": "PurchaseOrder",
            "properties": {{
                "po_number": "PO-12345",
                "vendor": "Acme Corp",
                "amount": 5000.0,
                "currency": "USD"
            }},
            "confidence": 0.95
        }}
    ]
}}
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
        Extract entities from a batch of emails using parallel processing.

        Performance Targets:
        - 50 emails in <2 minutes (2.4s per email)
        - 30% cost reduction via batch processing

        Args:
            emails: List of normalized email dicts
            tenant_id: Tenant UUID
            workspace_id: Workspace UUID
            batch_id: Optional batch ID for grouping

        Returns:
            List of all extracted entities from all emails
        """
        if not emails:
            return []

        # Split into batches of 10 for parallel processing
        batch_size = 10
        all_entities = []

        logger.info(f"Starting batch extraction: {len(emails)} emails in batches of {batch_size}")

        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]

            # Process batch in parallel
            tasks = [
                self.extract_from_email(
                    email,
                    tenant_id,
                    workspace_id,
                    batch_id=batch_id or f"batch-{i // batch_size}"
                )
                for email in batch
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Aggregate results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch extraction error: {result}")
                elif isinstance(result, list):
                    all_entities.extend(result)

            logger.info(f"Batch {i // batch_size + 1} complete: {len(all_entities)} entities so far")

        logger.info(f"Batch extraction complete: {len(all_entities)} entities from {len(emails)} emails")
        return all_entities

    def _get_cached_prompt(self, email_data: Dict[str, Any]) -> Optional[str]:
        """
        Get cached prompt for similar email.

        Args:
            email_data: Email data

        Returns:
            Cached prompt or None
        """
        # Generate cache key from email category
        category = self._classify_email_category(email_data)
        return self.prompt_cache.get(category)

    def _cache_prompt(self, email_data: Dict[str, Any], prompt: str) -> None:
        """
        Cache prompt for future use.

        Args:
            email_data: Email data
            prompt: Generated prompt
        """
        # Generate cache key from email category
        category = self._classify_email_category(email_data)
        self.prompt_cache[category] = prompt
        logger.debug(f"Cached prompt for category: {category} (cache size: {len(self.prompt_cache)})")

    def _classify_email_category(self, email_data: Dict[str, Any]) -> str:
        """
        Classify email into category for caching.

        Categories: purchase_order, security_event, invoice, ticket, lead, general

        Args:
            email_data: Email data

        Returns:
            Category string
        """
        subject = email_data.get('subject', '').lower()
        body = email_data.get('body', '')[:500].lower()

        # Check for purchase orders
        if any(keyword in subject or keyword in body for keyword in ['po', 'purchase order', 'purchase order #']):
            return 'purchase_order'

        # Check for security events
        if any(keyword in subject or keyword in body for keyword in ['security', 'alert', 'unusual login', 'malware', 'phishing']):
            return 'security_event'

        # Check for invoices
        if any(keyword in subject or keyword in body for keyword in ['invoice', 'payment', 'bill', 'receipt']):
            return 'invoice'

        # Check for tickets
        if any(keyword in subject or keyword in body for keyword in ['ticket', 'issue', 'support', 'help']):
            return 'ticket'

        # Check for leads
        if any(keyword in subject or keyword in body for keyword in ['lead', 'prospect', 'inquiry', 'demo']):
            return 'lead'

        # Default category
        return 'general'

    def _get_cache_hit_rate(self) -> float:
        """
        Calculate cache hit rate.

        Returns:
            Hit rate (0.0 to 1.0)
        """
        if self.cache_stats["total"] == 0:
            return 0.0
        return self.cache_stats["hits"] / self.cache_stats["total"]

    def _analyze_email_complexity(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze email complexity for model selection.

        Factors:
        - Word count (simple: <100, complex: >500)
        - Structure (attachments, multiple recipients)
        - Special keywords (legal, technical, financial)

        Args:
            email_data: Email data

        Returns:
            Complexity analysis dict
        """
        body = email_data.get('body', '')
        subject = email_data.get('subject', '')
        to_recipients = email_data.get('to', [])
        cc_recipients = email_data.get('cc', [])
        has_attachments = email_data.get('attachments', [])

        # Word count
        word_count = len(body.split())

        # Recipient count
        recipient_count = len(to_recipients) + len(cc_recipients)

        # Check for complex keywords
        complex_keywords = [
            'legal', 'contract', 'agreement', 'liability',
            'technical', 'specification', 'architecture', 'integration',
            'financial', 'forecast', 'budget', 'revenue'
        ]
        has_complex_keywords = any(keyword in body.lower() for keyword in complex_keywords)

        # Calculate complexity score (0-100)
        complexity_score = 0
        complexity_score += min(word_count / 10, 50)  # Up to 50 points for length
        complexity_score += min(recipient_count * 2, 20)  # Up to 20 points for recipients
        complexity_score += len(has_attachments) * 5  # 5 points per attachment
        if has_complex_keywords:
            complexity_score += 20  # 20 points for complex keywords

        return {
            "word_count": word_count,
            "recipient_count": recipient_count,
            "attachment_count": len(has_attachments),
            "has_complex_keywords": has_complex_keywords,
            "complexity_score": min(complexity_score, 100)
        }

    def _select_model(self, email_data: Dict[str, Any]) -> str:
        """
        Select optimal LLM model based on email complexity.

        Model Selection Strategy:
        - GPT-4o-mini: Simple emails (<200 words, no complex keywords)
        - GPT-4o: Complex emails (>200 words, complex keywords, attachments)

        Cost Difference:
        - GPT-4o-mini: $0.15/1M input tokens
        - GPT-4o: $2.50/1M input tokens (16.7x more expensive)

        Args:
            email_data: Email data

        Returns:
            Model name (gpt-4o or gpt-4o-mini)
        """
        if not self.enable_model_selection:
            return self.model

        # Analyze complexity
        complexity = self._analyze_email_complexity(email_data)

        # Select model based on complexity
        if complexity["complexity_score"] < 40:
            # Simple email - use mini model
            selected_model = "gpt-4o-mini"
        else:
            # Complex email - use full model
            selected_model = "gpt-4o"

        # Track statistics
        self.model_stats[selected_model] += 1
        self.model_stats["total"] += 1

        logger.debug(
            f"Model selection: {selected_model} "
            f"(complexity: {complexity['complexity_score']:.0f}/100, "
            f"mini rate: {self._get_mini_model_rate():.1%})"
        )

        return selected_model

    def _get_mini_model_rate(self) -> float:
        """
        Calculate rate of GPT-4o-mini usage.

        Returns:
            Mini model usage rate (0.0 to 1.0)
        """
        if self.model_stats["total"] == 0:
            return 0.0
        return self.model_stats["gpt-4o-mini"] / self.model_stats["total"]

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance optimization statistics.

        Returns:
            Statistics dict with cache and model metrics
        """
        return {
            "prompt_cache": {
                "hit_rate": self._get_cache_hit_rate(),
                "hits": self.cache_stats["hits"],
                "misses": self.cache_stats["misses"],
                "total": self.cache_stats["total"],
                "cache_size": len(self.prompt_cache)
            },
            "model_selection": {
                "mini_rate": self._get_mini_model_rate(),
                "gpt_4o_mini_count": self.model_stats["gpt-4o-mini"],
                "gpt_4o_count": self.model_stats["gpt-4o"],
                "total": self.model_stats["total"]
            }
        }

    def reset_stats(self) -> None:
        """Reset performance statistics."""
        self.cache_stats = {"hits": 0, "misses": 0, "total": 0}
        self.model_stats = {"gpt-4o": 0, "gpt-4o-mini": 0, "total": 0}
        logger.info("Performance statistics reset")
