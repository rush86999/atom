"""
Schema-Aware SQL Generator for Entity Query Service.

Generates SQL queries from natural language using LLMService.
Custom NL2SQL implementation (provider-agnostic, BYOK-enabled).
"""
import logging
import re
import sqlparse
from typing import Dict, Any

from core.llm_service import LLMService

logger = logging.getLogger(__name__)


class SchemaAwareSQLGenerator:
    """
    Generate SQL queries from natural language with schema awareness.

    Uses LLMService for provider-agnostic LLM calls with BYOK support.
    Always injects user_id filter (cannot be bypassed by agent).
    """

    def __init__(self, db, workspace_id: str, llm_service: LLMService):
        """
        Initialize SQL generator.

        Args:
            db: SQLAlchemy database session
            workspace_id: Workspace ID for isolation (Upstream primary key)
            llm_service: LLMService instance for NL2SQL generation
        """
        self.db = db
        self.workspace_id = workspace_id
        self.llm_service = llm_service

    async def generate_sql(
        self,
        entity_type_slug: str,
        question: str,
        json_schema: Dict[str, Any],
        additional_context: str = ""
    ) -> str:
        """Generate SQL query from natural language question."""
        logger.info(f"Generating SQL for entity_type={entity_type_slug}, question={question[:50]}...")

        prompt = self._build_schema_aware_prompt(json_schema, entity_type_slug, question, additional_context)

        try:
            system_instruction = (
                "You are a SQL expert. Generate SELECT queries only. "
                "Use proper SQL syntax. Return only the SQL query, no explanation."
            )

            llm_response = await self.llm_service.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.0,
                max_tokens=500
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise ValueError(f"Failed to generate SQL: {e}")

        sql_query = self._extract_sql_from_llm_response(llm_response)
        if not sql_query:
            raise ValueError("LLM did not generate a valid SQL query")

        # Inject workspace_id filter (MANDATORY)
        sql_with_workspace = self._inject_workspace_filter(sql_query, self.workspace_id)

        return sql_with_workspace

    def _build_schema_aware_prompt(
        self,
        json_schema: Dict[str, Any],
        entity_type_slug: str,
        question: str,
        additional_context: str = ""
    ) -> str:
        """Build schema-aware few-shot prompt for LLM."""
        properties = json_schema.get('properties', {})
        fields_info = []

        for field_name, field_def in properties.items():
            field_type = field_def.get('type', 'unknown')
            description = field_def.get('description', '')
            fields_info.append(f"- {field_name} ({field_type}): {description}" if description else f"- {field_name} ({field_type})")

        fields_text = "\n".join(fields_info)
        context_section = f"\n\nKnowledge Graph Context:\n{additional_context}" if additional_context else ""

        prompt = f"""Table: {entity_type_slug}

Available fields:
{fields_text}

System fields (always available): id, workspace_id, created_at, updated_at{context_section}

Task: Generate a SQL query to answer the following question.

Question: {question}

A:"""
        return prompt

    def _inject_workspace_filter(self, sql: str, workspace_id: str) -> str:
        """Inject workspace_id filter into SQL query."""
        try:
            parsed = sqlparse.parse(sql)[0]
        except Exception:
            return f"{sql} AND workspace_id = '{workspace_id}'"

        has_where = any(t.ttype is sqlparse.tokens.Keyword and t.value.upper() == 'WHERE' for t in parsed.tokens)

        if has_where:
            sql_with_workspace = re.sub(r'\bWHERE\b', f"WHERE workspace_id = '{workspace_id}' AND", sql, count=1, flags=re.I)
        else:
            match = re.search(r'\s+(GROUP BY|ORDER BY|LIMIT|OFFSET|HAVING)\b', sql, re.I)
            if match:
                pos = match.start()
                sql_with_workspace = f"{sql[:pos]} WHERE workspace_id = '{workspace_id}' {sql[pos:]}"
            else:
                sql_with_workspace = f"{sql} WHERE workspace_id = '{workspace_id}'"

        return sql_with_workspace

    def _extract_sql_from_llm_response(self, response: str) -> str:
        """Extract SQL query from LLM response."""
        if not response: return ""
        response = response.strip()
        
        match = re.search(r'```sql\s*(.*?)\s*```', response, re.S | re.I)
        if match: return match.group(1).strip()
        
        match = re.search(r'```\s*(.*?)\s*```', response, re.S)
        if match and match.group(1).strip().upper().startswith('SELECT'):
            return match.group(1).strip()

        match = re.search(r'(SELECT\s+.*?(?:;|$))', response, re.I | re.S)
        if match:
            sql = match.group(1).strip()
            if sql.endswith(';'): sql = sql[:-1].strip()
            return sql
            
        return ""
