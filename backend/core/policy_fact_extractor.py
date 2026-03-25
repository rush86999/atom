"""
Policy Fact Extractor

AI-powered extraction of business facts from parsed policy documents.
Uses LLM to identify discrete, actionable business rules with citations.
"""

import logging
import json
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from core.llm_service import get_llm_service

logger = logging.getLogger(__name__)

class ExtractedFact(BaseModel):
    """A business fact extracted from a document"""
    fact: str
    domain: str  # finance, hr, operations, compliance, etc.
    page_or_section: Optional[str] = None
    confidence: float = 0.8
    
class ExtractionResult(BaseModel):
    """Result of fact extraction from a document"""
    facts: List[ExtractedFact]
    source_document: str
    total_pages: Optional[int] = None
    extraction_time: float = 0.0


class PolicyFactExtractor:
    """
    Extracts business facts from parsed policy documents using LLM.
    """
    
    EXTRACTION_PROMPT = """You are a policy analyst extracting business facts from documents.

Your task is to identify discrete, actionable business rules or policies.

For each fact:
1. State the rule clearly and concisely (one sentence)
2. Identify the domain: finance, hr, operations, compliance, legal, security, or general
3. Note confidence (0.0-1.0) based on how clearly the rule is stated

IMPORTANT:
- Only extract explicit rules, not general statements
- Each fact should be actionable (something someone must do/not do, or a threshold/limit)
- Skip vague statements like "we value quality" - those are not facts

Return JSON array:
[
  {"fact": "All invoices over $500 require VP approval", "domain": "finance", "confidence": 0.95},
  {"fact": "PTO requests must be submitted 2 weeks in advance", "domain": "hr", "confidence": 0.9}
]

If no clear business facts are found, return an empty array: []

Document content:
{document_text}
"""

    def __init__(self, workspace_id: str = "default", tenant_id: str = "default"):
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self.llm = get_llm_service(workspace_id=workspace_id, tenant_id=tenant_id)
    
    async def extract_facts_from_text(
        self,
        text: str,
        source_document: str,
        page_number: Optional[int] = None,
        chunk_size: int = 8000
    ) -> List[ExtractedFact]:
        """Extract business facts from document text."""
        start_time = time.time()
        
        all_facts: List[ExtractedFact] = []
        
        # Split text into chunks if needed
        chunks = self._split_text(text, chunk_size)
        
        for i, chunk in enumerate(chunks):
            try:
                prompt = self.EXTRACTION_PROMPT.format(document_text=chunk)
                
                # Use unified generation with preference for quality models for extraction
                response_text = await self.llm.generate(
                    prompt=prompt,
                    system_instruction="You are a policy extraction expert. Return only JSON.",
                    model="quality",
                    temperature=0.1
                )
                
                # Parse JSON array from response
                facts_data = self._extract_json(response_text)
                
                for fact_data in facts_data:
                    if isinstance(fact_data, dict) and fact_data.get("fact"):
                        fact = ExtractedFact(
                            fact=fact_data["fact"],
                            domain=fact_data.get("domain", "general"),
                            page_or_section=f"p{page_number}" if page_number else f"chunk_{i+1}",
                            confidence=float(fact_data.get("confidence", 0.8))
                        )
                        all_facts.append(fact)
                        
            except Exception as e:
                logger.error(f"Error extracting facts from chunk {i}: {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"Extracted {len(all_facts)} facts from '{source_document}' in {elapsed:.2f}s")
        
        return all_facts
    
    async def extract_facts_from_document(
        self,
        document_path: str,
        user_id: str = "system"
    ) -> ExtractionResult:
        """Extract facts from a document file using Docling processor."""
        start_time = time.time()
        
        try:
            from core.docling_processor import get_docling_processor
            processor = get_docling_processor()
        except ImportError:
            logger.error("Docling processor not available")
            return ExtractionResult(facts=[], source_document=document_path, extraction_time=0.0)
        
        if not processor.is_available:
            logger.error("Docling processor not available")
            return ExtractionResult(facts=[], source_document=document_path, extraction_time=0.0)
        
        # Parse the document
        parse_result = await processor.process_document(
            source=document_path,
            export_format="markdown"
        )
        
        if not parse_result.get("success"):
            logger.error(f"Document parsing failed: {parse_result.get('error')}")
            return ExtractionResult(facts=[], source_document=document_path, extraction_time=0.0)
        
        text_content = parse_result.get("content", "")
        page_count = parse_result.get("page_count")
        
        # Extract facts from parsed text
        facts = await self.extract_facts_from_text(
            text=text_content,
            source_document=document_path
        )
        
        elapsed = time.time() - start_time
        
        return ExtractionResult(
            facts=facts,
            source_document=document_path,
            total_pages=page_count,
            extraction_time=elapsed
        )
    
    def _split_text(self, text: str, chunk_size: int) -> List[str]:
        """Split text into chunks."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        current_chunk = ""
        paragraphs = text.split("\n\n")
        
        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _extract_json(self, response_text: str) -> List[Dict]:
        """Robustly extract JSON list from text."""
        try:
            # Try direct parse
            return json.loads(response_text)
        except Exception:
            # Try to find array boundaries
            start = response_text.find("[")
            end = response_text.rfind("]") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(response_text[start:end])
                except Exception:
                    pass
        return []


# Global registry
_extractors: Dict[str, PolicyFactExtractor] = {}

def get_policy_fact_extractor(workspace_id: str = "default", tenant_id: str = "default") -> PolicyFactExtractor:
    """Get or create a PolicyFactExtractor for the workspace."""
    cache_key = f"{workspace_id}:{tenant_id}"
    if cache_key not in _extractors:
        _extractors[cache_key] = PolicyFactExtractor(workspace_id, tenant_id)
    return _extractors[cache_key]
