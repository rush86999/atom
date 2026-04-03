"""
Multi-Entity SQL Generator for JOIN Queries.

Extends SchemaAwareSQLGenerator to support multi-table JOIN queries
with GraphRAG relationship validation and user_id injection for all tables.
"""
import logging
import re
import sqlparse
from typing import Dict, Any, List

from core.schema_aware_sql_generator import SchemaAwareSQLGenerator
from core.multi_entity_validator import MultiEntityValidator
from core.llm_service import LLMService

logger = logging.getLogger(__name__)


class MultiEntitySQLGenerator(SchemaAwareSQLGenerator):
    """
    Generate multi-table JOIN SQL queries with GraphRAG validation.
    """

    def __init__(
        self,
        db,
        workspace_id: str,
        llm_service: LLMService,
        validator: MultiEntityValidator
    ):
        """
        Initialize multi-entity SQL generator.

        Args:
            db: SQLAlchemy database session
            workspace_id: Workspace ID for isolation (Upstream primary key)
            llm_service: LLMService instance for NL2SQL generation
            validator: MultiEntityValidator for relationship validation
        """
        super().__init__(db, workspace_id, llm_service)
        self.validator = validator

    async def generate_multi_entity_sql(
        self,
        entity_types: List[str],
        question: str,
        json_schemas: Dict[str, Dict]
    ) -> str:
        """Generate multi-entity JOIN SQL query."""
        logger.info(f"Generating multi-entity SQL: {entity_types}, question={question[:50]}...")

        # Step 1: Validate all entity pair relationships exist
        for i in range(len(entity_types) - 1):
            self.validator.validate_relationship_exists(entity_types[i], entity_types[i + 1])

        # Step 2: Build multi-entity few-shot prompt
        prompt = self._build_multi_entity_prompt(entity_types, question, json_schemas)

        # Step 3: Generate SQL via LLMService
        try:
            system_instruction = (
                "You are a SQL expert. Generate SELECT queries with JOINs. "
                "Use proper SQL syntax. Use table aliases for disambiguation. "
                "Return only the SQL query, no explanation."
            )

            llm_response = await self.llm_service.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.0,
                max_tokens=800
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise ValueError(f"Failed to generate multi-entity SQL: {e}")

        # Step 4: Extract SQL
        sql_query = self._extract_sql_from_llm_response(llm_response)
        if not sql_query:
            raise ValueError("LLM did not generate a valid SQL query")

        # Step 5: Inject workspace_id filters for ALL tables
        sql_with_workspace = self._inject_multi_workspace_filters(sql_query)

        logger.info(f"Generated multi-entity SQL: {sql_with_workspace[:150]}...")

        return sql_with_workspace

    def _build_multi_entity_prompt(
        self,
        entity_types: List[str],
        question: str,
        json_schemas: Dict
    ) -> str:
        """Build multi-entity few-shot prompt for LLM."""
        schema_blocks = []
        for entity_type in entity_types:
            schema = json_schemas.get(entity_type, {})
            properties = schema.get('properties', {})
            fields_info = [f"  - {f} ({d.get('type', 'unknown')})" for f, d in properties.items()]
            fields_text = "\n".join(fields_info)
            schema_blocks.append(f"Table: {entity_type}\nAvailable fields:\n{fields_text}\n\nSystem fields: id, user_id, created_at, updated_at")

        schemas_text = "\n\n".join(schema_blocks)
        prompt = f"""{schemas_text}

Task: Generate a SQL query with JOINs to answer the following question.
Requirements:
- Use table aliases (e.g., v for vendors)
- Use INNER JOIN by default
- Always filter by workspace_id for ALL tables
- Use proper JOIN conditions (e.g., ON {entity_a[0]}.id = {entity_b[0]}.{entity_a}_id)
A:"""
        return prompt

    def _inject_multi_workspace_filters(self, sql: str) -> str:
        """Inject workspace_id filters for all tables in JOIN query."""
        aliases = self._extract_table_aliases(sql)
        if not aliases:
            return self._inject_workspace_filter(sql, self.workspace_id)

        workspace_filters = " AND ".join([f"{alias}.workspace_id = '{self.workspace_id}'" for alias in aliases])

        try:
            parsed = sqlparse.parse(sql)[0]
        except Exception:
            return f"{sql} AND {workspace_filters}"

        has_where = any(t.ttype is sqlparse.tokens.Keyword and t.value.upper() == 'WHERE' for t in parsed.tokens)

        if has_where:
            sql_with_workspace = re.sub(r'\bWHERE\b', f'WHERE {workspace_filters} AND', sql, count=1, flags=re.I)
        else:
            match = re.search(r'\s+(GROUP BY|ORDER BY|LIMIT|OFFSET|HAVING)\b', sql, re.I)
            if match:
                pos = match.start()
                sql_with_workspace = f"{sql[:pos]} WHERE {workspace_filters} {sql[pos:]}"
            else:
                sql_with_workspace = f"{sql} WHERE {workspace_filters}"

        return sql_with_workspace

    def _extract_table_aliases(self, sql: str) -> List[str]:
        """Extract table aliases from SQL query."""
        aliases = []
        # Simple extraction via regex for robustness
        pattern = r'(?:FROM|JOIN)\s+(\w+)(?:\s+AS\s+)?(\w+)?'
        matches = re.finditer(pattern, sql, re.I)
        for match in matches:
            table_name = match.group(1)
            alias = match.group(2)
            if alias: aliases.append(alias)
            elif table_name: aliases.append(table_name)
        
        seen = set()
        return [x for x in aliases if not (x in seen or seen.add(x))]
