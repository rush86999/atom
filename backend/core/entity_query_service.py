"""
Entity Query Service for Natural Language SQL Generation.

Orchestrates NL2SQL with security validation:
1. Load entity schema
2. Generate SQL from natural language
3. Validate SQL against schema
4. Sanitize SQL for security
5. Execute query with user isolation
6. Format results as entity instances
"""
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.entity_type_service import EntityTypeService
from core.sql_validator import SQLValidator, SQLSanitizer, SecurityError
from core.schema_aware_sql_generator import SchemaAwareSQLGenerator
from core.llm_service import LLMService
from core.multi_entity_validator import MultiEntityValidator
from core.multi_entity_sql_generator import MultiEntitySQLGenerator
from core.agent_graphrag_service import AgentGraphRAGService
from core.audit_service import AuditService

logger = logging.getLogger(__name__)


class EntityQueryService:
    """
    Natural language query service for dynamic entities.
    """

    def __init__(self, db: Session, workspace_id: str, agent_id: str):
        """
        Initialize entity query service.

        Args:
            db: SQLAlchemy database session
            workspace_id: Workspace ID for isolation (Upstream primary key)
            agent_id: Agent ID for audit logging
        """
        self.db = db
        self.workspace_id = workspace_id
        self.agent_id = agent_id

        self.entity_type_service = EntityTypeService(db=db)
        self.sql_validator = SQLValidator()
        self.sql_sanitizer = SQLSanitizer()
        self.llm_service = LLMService(db=db, workspace_id=workspace_id)
        self.multi_entity_validator = MultiEntityValidator(db=db, workspace_id=workspace_id)
        self.graphrag_service = AgentGraphRAGService(db=db, workspace_id=workspace_id, agent_id=agent_id)
        self.audit_service = AuditService(db=db)

    async def natural_language_query(
        self,
        entity_type_slug: str,
        question: str
    ) -> List[Dict[str, Any]]:
        """Query entities using natural language."""
        logger.info(f"Natural language query: entity_type={entity_type_slug}, question={question[:50]}...")

        entity_type = self.entity_type_service.get_entity_type(workspace_id=self.workspace_id, slug=entity_type_slug)
        if not entity_type:
            raise ValueError(f"Entity type '{entity_type_slug}' not found for workspace '{self.workspace_id}'")

        json_schema = entity_type.json_schema
        sql_generator = SchemaAwareSQLGenerator(db=self.db, workspace_id=self.workspace_id, llm_service=self.llm_service)

        sql_query = await sql_generator.generate_sql(entity_type_slug=entity_type_slug, question=question, json_schema=json_schema)
        
        self.sql_validator.validate_sql_against_schema(sql_query, json_schema)
        self.sql_sanitizer.sanitize_sql(sql_query)

        await self.audit_service.log_sql_query(
            workspace_id=self.workspace_id,
            agent_id=self.agent_id,
            entity_type_slug=entity_type_slug,
            sql_query=sql_query[:1000],
            question=question[:500],
            outcome="success"
        )

        try:
            result = self.db.execute(text(sql_query))
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
        except SQLAlchemyError as e:
            logger.error(f"Query execution failed: {e}")
            raise SQLAlchemyError(f"Query execution failed: {e}")

    async def multi_entity_query(
        self,
        entity_types: List[str],
        question: str
    ) -> List[Dict[str, Any]]:
        """Query multiple related entities using natural language."""
        logger.info(f"Multi-entity query: entity_types={entity_types}, question={question[:50]}...")

        schemas = {}
        for slug in entity_types:
            entity_type = self.entity_type_service.get_entity_type(workspace_id=self.workspace_id, slug=slug)
            if not entity_type: raise ValueError(f"Entity type '{slug}' not found.")
            schemas[slug] = entity_type.json_schema

        sql_generator = MultiEntitySQLGenerator(db=self.db, workspace_id=self.workspace_id, llm_service=self.llm_service, validator=self.multi_entity_validator)
        sql_query = await sql_generator.generate_multi_entity_sql(entity_types=entity_types, question=question, json_schemas=schemas)

        for slug, schema in schemas.items():
            self.sql_validator.validate_sql_against_schema(sql_query, schema)
        self.sql_sanitizer.sanitize_sql(sql_query)

        try:
            result = self.db.execute(text(sql_query))
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
        except SQLAlchemyError as e:
            logger.error(f"Multi-entity query execution failed: {e}")
            raise
