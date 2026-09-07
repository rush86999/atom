"""Regression: KnowledgeExtractor must never receive a service object as
workspace_id.

Observed Sep 5, 2026: KnowledgeIngestionManager called
KnowledgeExtractor(self.ai_service) positionally, binding
RealAIWorkflowService into KnowledgeExtractor.__init__(workspace_id=...).
The object then flowed into LLMService -> BYOKHandler -> the tenant-plan
Workspace query, producing "Failed to fetch tenant plan: Error binding
parameter 1: type 'RealAIWorkflowService' is not supported" on EVERY
extraction call (plan gating silently degraded to free-tier defaults).
document_learner had the identical positional-call bug.
"""
import os
os.environ.setdefault("TESTING", "1")

from core.knowledge_ingestion import KnowledgeIngestionManager
from core.document_learner import DocumentLifecycleLearner


def test_ingestion_manager_extractor_gets_string_workspace():
    manager = KnowledgeIngestionManager(workspace_id="ws-main")
    assert isinstance(manager.extractor.workspace_id, str)
    assert manager.extractor.workspace_id == "ws-main"


def test_document_learner_extractor_defaults_to_workspace_string():
    # The old bug bound the ai_service object here; any str (the "default"
    # fallback) proves the fix. A non-str would re-trigger the SQL bind error.
    learner = DocumentLifecycleLearner()
    assert isinstance(learner.extractor.workspace_id, str)
