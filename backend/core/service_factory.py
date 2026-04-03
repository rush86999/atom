"""
Service Factory for Atom Platform

Provides centralized service instantiation to eliminate code duplication.
Ensures efficient resource management and consistent service configuration.
"""

import logging
import threading
from typing import Dict, Optional, Any
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import User
from core.agent_context_resolver import AgentContextResolver
from core.governance_cache import GovernanceCache
from services.canvas_context_service import CanvasContextService
from core.canvas_recording_service import CanvasRecordingService
from core.canvas_presentation_summary import CanvasPresentationSummaryService
from core.activity_publisher import ActivityPublisher
from core.agent_world_model import WorldModelService
from core.knowledge_extractor import KnowledgeExtractor
from core.graphrag_engine import GraphRAGEngine
from core.llm_service import LLMService
from core.social_post_generator import SocialPostGenerator
from core.agents.queen_agent import QueenAgent
from core.agents.skill_creation_agent import SkillCreationAgent
from core.agents.king_agent import KingAgent
from core.agents.autoresearch_agent import AutoresearchAgent
from core.group_reflection_service import GroupReflectionService
from core.goal_engine import GoalEngine
from core.atom_meta_agent import AtomMetaAgent
from core.integration_catalog_service import IntegrationCatalogService
from core.integration_registry import IntegrationRegistry
from core.budget_enforcement_service import BudgetEnforcementService
from core.policy_search_service import PGPolicySearchService
from core.docling_processor import DoclingDocumentProcessor
from core.messaging_action_dispatcher import MessagingActionDispatcher
from core.universal_communication_bridge import UniversalCommunicationBridge
from core.episode_service import EpisodeService
from core.integrations.adapters.zoho import ZohoAdapter
from core.integrations.adapters.hubspot import HubSpotAdapter
from core.integrations.adapters.notion import NotionAdapter
from core.integrations.adapters.airtable import AirtableAdapter
from core.integrations.adapters.jira import JiraAdapter
from core.hybrid_data_ingestion import HybridDataIngestionService

logger = logging.getLogger(__name__)


class ServiceFactory:
    """
    Centralized factory for creating and managing service instances.

    Uses thread-local storage to ensure thread safety while allowing
    service instance reuse within a single thread/request context.

    Example:
        # In API routes
        @router.post("/agent/{agent_id}/execute")
        async def execute_agent(agent_id: str, db: Session = Depends(get_db)):
            governance = ServiceFactory.get_governance_service(db)
            can_execute = governance.can_execute_action(agent_id, 3)

        # In core services
        def process_agent_request(agent_id: str, db: Session):
            resolver = ServiceFactory.get_context_resolver(db)
            context = resolver.resolve_context(agent_id)
    """

    # Thread-local storage for service instances
    _thread_local = threading.local()

    # Global singletons (thread-safe services)
    _governance_cache: Optional[GovernanceCache] = None
    _cache_lock = threading.Lock()

    @classmethod
    def get_governance_service(cls, db: Session, workspace_id: str = "default", tenant_id: Optional[str] = None) -> AgentGovernanceService:
        """Get or create an AgentGovernanceService instance."""
        if not hasattr(cls._thread_local, 'governance_service'):
            publisher = cls.get_activity_publisher()
            cls._thread_local.governance_service = AgentGovernanceService(
                db, 
                workspace_id=workspace_id, 
                tenant_id=tenant_id, 
                activity_publisher=publisher
            )
        return cls._thread_local.governance_service

    @classmethod
    def get_context_resolver(cls, db: Session) -> AgentContextResolver:
        """
        Get or create an AgentContextResolver instance.

        Args:
            db: Database session

        Returns:
            AgentContextResolver instance
        """
        if not hasattr(cls._thread_local, 'context_resolver'):
            cls._thread_local.context_resolver = AgentContextResolver(db)
        return cls._thread_local.context_resolver

    @classmethod
    def get_governance_cache(cls) -> GovernanceCache:
        """
        Get or create the global GovernanceCache instance.

        The cache is a singleton since it's thread-safe and shared
        across all requests.

        Returns:
            GovernanceCache instance
        """
        if cls._governance_cache is None:
            with cls._cache_lock:
                # Double-check locking pattern
                if cls._governance_cache is None:
                    cls._governance_cache = GovernanceCache()
                    logger.info("Initialized global GovernanceCache")
        return cls._governance_cache

    @classmethod
    def clear_thread_local(cls):
        """
        Clear thread-local service instances.

        Should be called at the end of each request to prevent memory leaks.
        This is particularly important for long-running server processes.

        Example:
            # In FastAPI middleware
            @app.middleware("http")
            async def clear_services(request: Request, call_next):
                response = await call_next(request)
                ServiceFactory.clear_thread_local()
                return response
        """
        if hasattr(cls._thread_local, 'governance_service'):
            delattr(cls._thread_local, 'governance_service')
        if hasattr(cls._thread_local, 'context_resolver'):
            delattr(cls._thread_local, 'context_resolver')
        if hasattr(cls._thread_local, 'canvas_context_service'):
            delattr(cls._thread_local, 'canvas_context_service')
        if hasattr(cls._thread_local, 'canvas_recording_service'):
            delattr(cls._thread_local, 'canvas_recording_service')
        if hasattr(cls._thread_local, 'canvas_summary_service'):
            delattr(cls._thread_local, 'canvas_summary_service')
        if hasattr(cls._thread_local, 'episode_service'):
            delattr(cls._thread_local, 'episode_service')
        if hasattr(cls._thread_local, 'activity_publisher'):
            delattr(cls._thread_local, 'activity_publisher')
        if hasattr(cls._thread_local, 'social_post_generator'):
            delattr(cls._thread_local, 'social_post_generator')
        if hasattr(cls._thread_local, 'queen_agent'):
            delattr(cls._thread_local, 'queen_agent')
        if hasattr(cls._thread_local, 'atom_meta_agent'):
            delattr(cls._thread_local, 'atom_meta_agent')
        if hasattr(cls._thread_local, 'zoho_adapter'):
            delattr(cls._thread_local, 'zoho_adapter')
        if hasattr(cls._thread_local, 'hubspot_adapter'):
            delattr(cls._thread_local, 'hubspot_adapter')
        if hasattr(cls._thread_local, 'notion_adapter'):
            delattr(cls._thread_local, 'notion_adapter')
        if hasattr(cls._thread_local, 'airtable_adapter'):
            delattr(cls._thread_local, 'airtable_adapter')
        if hasattr(cls._thread_local, 'jira_adapter'):
            delattr(cls._thread_local, 'jira_adapter')
        if hasattr(cls._thread_local, 'hybrid_ingestion'):
            delattr(cls._thread_local, 'hybrid_ingestion')
        if hasattr(cls._thread_local, 'integration_catalog'):
            delattr(cls._thread_local, 'integration_catalog')
        if hasattr(cls._thread_local, 'budget_enforcement'):
            delattr(cls._thread_local, 'budget_enforcement')
        if hasattr(cls._thread_local, 'policy_search'):
            delattr(cls._thread_local, 'policy_search')
        if hasattr(cls._thread_local, 'docling_processor'):
            delattr(cls._thread_local, 'docling_processor')
        if hasattr(cls._thread_local, 'messaging_dispatcher'):
            delattr(cls._thread_local, 'messaging_dispatcher')
        if hasattr(cls._thread_local, 'communication_bridge'):
            delattr(cls._thread_local, 'communication_bridge')


    @classmethod
    def get_canvas_context_service(cls, db: Session, tenant_id: str) -> CanvasContextService:
        """Get or create CanvasContextService instance."""
        if not hasattr(cls._thread_local, 'canvas_context_service'):
            cls._thread_local.canvas_context_service = CanvasContextService(db, tenant_id=tenant_id)
        return cls._thread_local.canvas_context_service

    @classmethod
    def get_canvas_recording_service(cls, db: Session, tenant_id: str) -> CanvasRecordingService:
        """Get or create CanvasRecordingService instance."""
        if not hasattr(cls._thread_local, 'canvas_recording_service'):
            cls._thread_local.canvas_recording_service = CanvasRecordingService(db, tenant_id=tenant_id)
        return cls._thread_local.canvas_recording_service

    @classmethod
    def get_canvas_summary_service(cls, db: Session, tenant_id: str) -> CanvasPresentationSummaryService:
        """Get or create CanvasPresentationSummaryService instance."""
        if not hasattr(cls._thread_local, 'canvas_summary_service'):
            cls._thread_local.canvas_summary_service = CanvasPresentationSummaryService(db)
        return cls._thread_local.canvas_summary_service

    @classmethod
    def get_episode_service(cls, db: Session, workspace_id: str = "default", tenant_id: str = "default") -> EpisodeService:
        """Get or create EpisodeService instance."""
        if not hasattr(cls._thread_local, 'episode_service'):
            publisher = cls.get_activity_publisher()
            cls._thread_local.episode_service = EpisodeService(db, tenant_api_key=None, activity_publisher=publisher)
        return cls._thread_local.episode_service

    @classmethod
    def get_activity_publisher(cls) -> ActivityPublisher:
        """Get or create ActivityPublisher instance."""
        if not hasattr(cls._thread_local, 'activity_publisher'):
            from core.activity_publisher import get_activity_publisher as get_pub
            cls._thread_local.activity_publisher = get_pub()
        return cls._thread_local.activity_publisher

    @classmethod
    def get_guardrails_service(cls, db: Session, workspace_id: str = "default", tenant_id: Optional[str] = None) -> Any:
        """Get or create AutonomousGuardrailService instance."""
        if not hasattr(cls._thread_local, 'guardrails_service'):
            from core.autonomous_guardrails import AutonomousGuardrailService
            cls._thread_local.guardrails_service = AutonomousGuardrailService(
                db, 
                workspace_id=workspace_id, 
                tenant_id=tenant_id
            )
        return cls._thread_local.guardrails_service

    @classmethod
    def get_memory_consolidation_service(cls, workspace_id: str = "default", tenant_id: Optional[str] = None) -> Any:
        """Get or create MemoryConsolidationService instance."""
        if not hasattr(cls._thread_local, 'memory_consolidation_service'):
            from core.memory_consolidation import MemoryConsolidationService
            cls._thread_local.memory_consolidation_service = MemoryConsolidationService(
                workspace_id=workspace_id, 
                tenant_id=tenant_id
            )
        return cls._thread_local.memory_consolidation_service

    @classmethod
    def get_world_model_service(cls, workspace_id: str = "default", tenant_id: str = "default") -> WorldModelService:
        """Get or create WorldModelService instance."""
        if not hasattr(cls._thread_local, 'world_model_service'):
            cls._thread_local.world_model_service = WorldModelService(workspace_id=workspace_id, tenant_id=tenant_id)
        return cls._thread_local.world_model_service

    @classmethod
    def get_knowledge_extractor(cls, workspace_id: Optional[str] = None, 
                                tenant_id: Optional[str] = None) -> KnowledgeExtractor:
        """Get or create KnowledgeExtractor instance."""
        if not hasattr(cls._thread_local, 'knowledge_extractor'):
            cls._thread_local.knowledge_extractor = KnowledgeExtractor(
                workspace_id=workspace_id,
                tenant_id=tenant_id
            )
        return cls._thread_local.knowledge_extractor

    @classmethod
    def get_graphrag_engine(cls, workspace_id: Optional[str] = None, 
                           tenant_id: Optional[str] = None) -> GraphRAGEngine:
        """Get or create GraphRAGEngine instance."""
        if not hasattr(cls._thread_local, 'graphrag_engine'):
            cls._thread_local.graphrag_engine = GraphRAGEngine(
                workspace_id=workspace_id,
                tenant_id=tenant_id
            )
        return cls._thread_local.graphrag_engine

    @classmethod
    def get_llm_service(cls, workspace_id: Optional[str] = None, 
                        tenant_id: Optional[str] = None) -> LLMService:
        """Get or create the global unified LLMService instance."""
        if not hasattr(cls._thread_local, 'llm_service'):
            cls._thread_local.llm_service = LLMService(
                workspace_id=workspace_id,
                tenant_id=tenant_id
            )
        return cls._thread_local.llm_service

    @classmethod
    def get_social_post_generator(cls, workspace_id: str = "default", tenant_id: str = "default") -> SocialPostGenerator:
        """Get or create SocialPostGenerator instance."""
        if not hasattr(cls._thread_local, 'social_post_generator'):
            cls._thread_local.social_post_generator = SocialPostGenerator(workspace_id=workspace_id, tenant_id=tenant_id)
        return cls._thread_local.social_post_generator

    @classmethod
    def get_queen_agent(cls, db: Session, workspace_id: str = "default", tenant_id: str = "default") -> QueenAgent:
        """Get or create QueenAgent instance."""
        if not hasattr(cls._thread_local, 'queen_agent'):
            llm = cls.get_llm_service(workspace_id=workspace_id, tenant_id=tenant_id)
            cls._thread_local.queen_agent = QueenAgent(db, llm, workspace_id=workspace_id, tenant_id=tenant_id)
        return cls._thread_local.queen_agent

    @classmethod
    def get_atom_meta_agent(cls, workspace_id: str = "default", tenant_id: str = "default", user: Optional[User] = None) -> AtomMetaAgent:
        """Get or create AtomMetaAgent instance."""
        if not hasattr(cls._thread_local, 'atom_meta_agent'):
            cls._thread_local.atom_meta_agent = AtomMetaAgent(workspace_id=workspace_id, tenant_id=tenant_id, user=user)
        return cls._thread_local.atom_meta_agent

    @classmethod
    def get_skill_creation_agent(cls, db: Session, workspace_id: str = "default", tenant_id: str = "default") -> SkillCreationAgent:
        """Get or create SkillCreationAgent instance."""
        if not hasattr(cls._thread_local, 'skill_creation_agent'):
            llm = cls.get_llm_service(workspace_id=workspace_id, tenant_id=tenant_id)
            cls._thread_local.skill_creation_agent = SkillCreationAgent(db, llm, workspace_id=workspace_id, tenant_id=tenant_id)
        return cls._thread_local.skill_creation_agent

    @classmethod
    def get_king_agent(cls, workspace_id: str = "default", tenant_id: str = "default", user: Optional[User] = None) -> KingAgent:
        """Get or create KingAgent instance."""
        if not hasattr(cls._thread_local, 'king_agent'):
            cls._thread_local.king_agent = KingAgent(workspace_id=workspace_id, tenant_id=tenant_id, user=user)
        return cls._thread_local.king_agent

    @classmethod
    def get_autoresearch_agent(cls, db: Session, workspace_id: str = "default", tenant_id: str = "default") -> AutoresearchAgent:
        """Get or create AutoresearchAgent instance."""
        if not hasattr(cls._thread_local, 'autoresearch_agent'):
            llm = cls.get_llm_service(workspace_id=workspace_id, tenant_id=tenant_id)
            cls._thread_local.autoresearch_agent = AutoresearchAgent(db, llm, workspace_id=workspace_id, tenant_id=tenant_id)
        return cls._thread_local.autoresearch_agent

    @classmethod
    def get_group_reflection_service(cls, db: Session) -> GroupReflectionService:
        """Get or create GroupReflectionService instance."""
        if not hasattr(cls._thread_local, 'group_reflection_service'):
            cls._thread_local.group_reflection_service = GroupReflectionService(db)
        return cls._thread_local.group_reflection_service

    @classmethod
    def get_push_notification_service(cls, db: Session, workspace_id: str = "default", tenant_id: Optional[str] = None) -> "PushNotificationService":
        """Get or create push notification service."""
        if not hasattr(cls._thread_local, 'push_notification_service'):
            from core.push_notifications import PushNotificationService
            cls._thread_local.push_notification_service = PushNotificationService(db, workspace_id=workspace_id, tenant_id=tenant_id)
        return cls._thread_local.push_notification_service

    @classmethod
    def get_workflow_analytics_engine(cls, db: Session, workspace_id: str = "default", tenant_id: Optional[str] = None) -> "WorkflowAnalyticsEngine":
        """Get or create WorkflowAnalyticsEngine instance."""
        if not hasattr(cls._thread_local, 'workflow_analytics_engine'):
            from core.workflow_analytics import WorkflowAnalyticsEngine
            cls._thread_local.workflow_analytics_engine = WorkflowAnalyticsEngine(db, workspace_id=workspace_id, tenant_id=tenant_id)
        return cls._thread_local.workflow_analytics_engine

    @classmethod
    def get_goal_engine(cls) -> GoalEngine:
        """Get or create GoalEngine instance."""
        if not hasattr(cls._thread_local, 'goal_engine'):
            cls._thread_local.goal_engine = GoalEngine()
        return cls._thread_local.goal_engine

    @classmethod
    def get_zoho_adapter(cls, db: Session, workspace_id: str = "default", instance_url: Optional[str] = None) -> ZohoAdapter:
        """Get or create Universal ZohoAdapter instance."""
        if not hasattr(cls._thread_local, 'zoho_adapter'):
            cls._thread_local.zoho_adapter = ZohoAdapter(db=db, workspace_id=workspace_id, instance_url=instance_url)
        return cls._thread_local.zoho_adapter

    @classmethod
    def get_hubspot_adapter(cls, db: Session, workspace_id: str = "default") -> HubSpotAdapter:
        """Get or create HubSpotAdapter instance."""
        if not hasattr(cls._thread_local, 'hubspot_adapter'):
            cls._thread_local.hubspot_adapter = HubSpotAdapter(db=db, workspace_id=workspace_id)
        return cls._thread_local.hubspot_adapter

    @classmethod
    def get_notion_adapter(cls, db: Session, workspace_id: str = "default") -> NotionAdapter:
        """Get or create NotionAdapter instance."""
        if not hasattr(cls._thread_local, 'notion_adapter'):
            cls._thread_local.notion_adapter = NotionAdapter(db=db, workspace_id=workspace_id)
        return cls._thread_local.notion_adapter

    @classmethod
    def get_airtable_adapter(cls, db: Session, workspace_id: str = "default") -> AirtableAdapter:
        """Get or create AirtableAdapter instance."""
        if not hasattr(cls._thread_local, 'airtable_adapter'):
            cls._thread_local.airtable_adapter = AirtableAdapter(db=db, workspace_id=workspace_id)
        return cls._thread_local.airtable_adapter

    @classmethod
    def get_jira_adapter(cls, db: Session, workspace_id: str = "default", site_url: Optional[str] = None) -> JiraAdapter:
        """Get or create JiraAdapter instance."""
        if not hasattr(cls._thread_local, 'jira_adapter'):
            cls._thread_local.jira_adapter = JiraAdapter(db=db, workspace_id=workspace_id, site_url=site_url)
        return cls._thread_local.jira_adapter

    @classmethod
    def get_hybrid_ingestion_service(cls, db: Session, workspace_id: str = "default", tenant_id: str = "default") -> HybridDataIngestionService:
        """Get or create HybridDataIngestionService instance."""
        if not hasattr(cls._thread_local, 'hybrid_ingestion'):
            cls._thread_local.hybrid_ingestion = HybridDataIngestionService(db=db, workspace_id=workspace_id, tenant_id=tenant_id)
        return cls._thread_local.hybrid_ingestion

    @classmethod
    def get_integration_catalog(cls, db: Session) -> IntegrationCatalogService:
        """Get or create IntegrationCatalogService instance."""
        if not hasattr(cls._thread_local, 'integration_catalog'):
            cls._thread_local.integration_catalog = IntegrationCatalogService(db)
        return cls._thread_local.integration_catalog

    @classmethod
    def get_budget_enforcement(cls, db: Session) -> BudgetEnforcementService:
        """Get or create BudgetEnforcementService instance."""
        if not hasattr(cls._thread_local, 'budget_enforcement'):
            cls._thread_local.budget_enforcement = BudgetEnforcementService(db)
        return cls._thread_local.budget_enforcement

    @classmethod
    def get_policy_search(cls, db: Session) -> PGPolicySearchService:
        """Get or create PGPolicySearchService instance."""
        if not hasattr(cls._thread_local, 'policy_search'):
            cls._thread_local.policy_search = PGPolicySearchService(db)
        return cls._thread_local.policy_search

    @classmethod
    def get_docling_processor(cls) -> DoclingDocumentProcessor:
        """Get or create DoclingDocumentProcessor instance (singleton)."""
        if not hasattr(cls._thread_local, 'docling_processor'):
            cls._thread_local.docling_processor = DoclingDocumentProcessor()
        return cls._thread_local.docling_processor

    @classmethod
    def get_integration_registry(cls) -> IntegrationRegistry:
        """Get the global IntegrationRegistry singleton."""
        return IntegrationRegistry()

    @classmethod
    def get_messaging_dispatcher(cls, db: Optional[Session] = None) -> MessagingActionDispatcher:
        """Get or create MessagingActionDispatcher instance."""
        if not hasattr(cls._thread_local, 'messaging_dispatcher'):
            cls._thread_local.messaging_dispatcher = MessagingActionDispatcher(db)
        return cls._thread_local.messaging_dispatcher

    @classmethod
    def get_communication_bridge(cls, db: Session) -> UniversalCommunicationBridge:
        """Get or create UniversalCommunicationBridge instance."""
        if not hasattr(cls._thread_local, 'communication_bridge'):
            cls._thread_local.communication_bridge = UniversalCommunicationBridge(db)
        return cls._thread_local.communication_bridge


class GovernanceServiceFactory:
    """
    Legacy factory for governance services.

    DEPRECATED: Use ServiceFactory.get_governance_service() instead.
    This class is maintained for backward compatibility.

    Example:
        # Old way (deprecated)
        governance = GovernanceServiceFactory.create(db)

        # New way (recommended)
        governance = ServiceFactory.get_governance_service(db)
    """

    _instances: Dict[int, AgentGovernanceService] = {}
    _lock = threading.Lock()

    @staticmethod
    def create(db: Session, workspace_id: str = "default", tenant_id: Optional[str] = None) -> AgentGovernanceService:
        """
        Create or reuse governance service instance for current thread.
        """
        thread_id = threading.current_thread().ident
        if thread_id not in GovernanceServiceFactory._instances:
            with GovernanceServiceFactory._lock:
                # Double-check locking
                if thread_id not in GovernanceServiceFactory._instances:
                    GovernanceServiceFactory._instances[thread_id] = AgentGovernanceService(
                        db, 
                        workspace_id=workspace_id, 
                        tenant_id=tenant_id
                    )
                    logger.debug(f"Created AgentGovernanceService for thread {thread_id}")

        return GovernanceServiceFactory._instances[thread_id]

    @staticmethod
    def clear_all():
        """
        Clear all cached governance service instances.

        DEPRECATED: Use ServiceFactory.clear_thread_local() instead.
        """
        GovernanceServiceFactory._instances.clear()
        logger.warning("Cleared all governance service instances (legacy factory)")


# Convenience functions for common service access patterns

def get_governance_service(db: Session, workspace_id: str = "default", tenant_id: Optional[str] = None) -> AgentGovernanceService:
    """
    Convenience function to get governance service.
    """
    return ServiceFactory.get_governance_service(db, workspace_id=workspace_id, tenant_id=tenant_id)


def get_context_resolver(db: Session) -> AgentContextResolver:
    """
    Convenience function to get context resolver.

    Args:
        db: Database session

    Returns:
        AgentContextResolver instance

    Example:
        resolver = get_context_resolver(db)
        context = resolver.resolve_context(agent_id)
    """
    return ServiceFactory.get_context_resolver(db)


def get_governance_cache() -> GovernanceCache:
    """
    Convenience function to get governance cache.

    Returns:
        GovernanceCache instance (singleton)

    Example:
        cache = get_governance_cache()
        cached_result = cache.get_cached_result(agent_id, action)
    """
    return ServiceFactory.get_governance_cache()


def get_episode_service(db: Session, workspace_id: str = "default", tenant_id: str = "default") -> EpisodeService:
    """
    Convenience function to get episode service.

    Args:
        db: Database session
        workspace_id: Workspace/tenant identifier

    Returns:
        EpisodeService instance
    """
    return ServiceFactory.get_episode_service(db, workspace_id=workspace_id, tenant_id=tenant_id)


def get_knowledge_extractor(workspace_id: Optional[str] = None, 
                           tenant_id: Optional[str] = None) -> KnowledgeExtractor:
    """
    Convenience function to get knowledge extractor.
    """
    return ServiceFactory.get_knowledge_extractor(workspace_id=workspace_id, tenant_id=tenant_id)


def get_graphrag_engine(workspace_id: Optional[str] = None, 
                       tenant_id: Optional[str] = None) -> GraphRAGEngine:
    """
    Convenience function to get GraphRAG engine.
    """
    return ServiceFactory.get_graphrag_engine(workspace_id=workspace_id, tenant_id=tenant_id)


def get_llm_service(workspace_id: Optional[str] = None, 
                    tenant_id: Optional[str] = None) -> LLMService:
    """
    Convenience function to get unified LLM service.
    """
    return ServiceFactory.get_llm_service(workspace_id=workspace_id, tenant_id=tenant_id)


def get_social_post_generator(workspace_id: str = "default", tenant_id: str = "default") -> SocialPostGenerator:
    """
    Convenience function to get social post generator.
    """
    return ServiceFactory.get_social_post_generator(workspace_id=workspace_id, tenant_id=tenant_id)


def get_queen_agent(db: Session, workspace_id: str = "default", tenant_id: str = "default") -> QueenAgent:
    """
    Convenience function to get Queen Agent.
    """
    return ServiceFactory.get_queen_agent(db, workspace_id=workspace_id, tenant_id=tenant_id)


def get_atom_meta_agent(workspace_id: str = "default", tenant_id: str = "default", user: Optional[User] = None) -> AtomMetaAgent:
    """
    Convenience function to get Atom Meta-Agent.
    """
    return ServiceFactory.get_atom_meta_agent(workspace_id=workspace_id, tenant_id=tenant_id, user=user)


def get_guardrails_service(db: Session, workspace_id: str = "default", tenant_id: Optional[str] = None) -> Any:
    """
    Convenience function to get autonomous guardrails service.
    """
    return ServiceFactory.get_guardrails_service(db, workspace_id=workspace_id, tenant_id=tenant_id)


def get_memory_consolidation_service(workspace_id: str = "default", tenant_id: Optional[str] = None) -> Any:
    """
    Convenience function to get memory consolidation service.
    """
    return ServiceFactory.get_memory_consolidation_service(workspace_id=workspace_id, tenant_id=tenant_id)
