"""
Formula Memory Manager for ATOM Platform
Provides hybrid Knowledge Graph + Vector Database storage for formulas.
Enables semantic search, dependency tracing, and agent access to reusable calculations.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Table name for formulas in LanceDB
FORMULAS_TABLE = "formulas"


class FormulaMemoryManager:
    """
    Manages formula storage and retrieval using a hybrid approach:
    - LanceDB: Vector embeddings for semantic search by use case
    - GraphRAG: Dependency edges for lineage tracing
    """

    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        self._lancedb = None
        self._graphrag = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of LanceDB and GraphRAG handlers."""
        if self._initialized:
            return

        try:
            from core.lancedb_handler import get_lancedb_handler
            self._lancedb = get_lancedb_handler(self.workspace_id)
            self._ensure_formulas_table()
        except Exception as e:
            logger.warning(f"LanceDB not available for formulas: {e}")
            self._lancedb = None

        try:
            from core.graphrag_engine import get_graphrag_engine
            self._graphrag = get_graphrag_engine(self.workspace_id)
        except Exception as e:
            logger.warning(f"GraphRAG not available for formula lineage: {e}")
            self._graphrag = None

        self._initialized = True

    def _ensure_formulas_table(self):
        """Create formulas table if it doesn't exist."""
        if self._lancedb is None:
            return

        try:
            table = self._lancedb.get_table(FORMULAS_TABLE)
            if table is None:
                self._lancedb.create_table(FORMULAS_TABLE)
                logger.info(f"Created '{FORMULAS_TABLE}' table in LanceDB")
        except Exception as e:
            logger.error(f"Failed to create formulas table: {e}")

    def add_formula(
        self,
        expression: str,
        name: str,
        domain: str = "general",
        use_case: str = "",
        parameters: List[Dict[str, str]] = None,
        example_input: Dict[str, Any] = None,
        example_output: Any = None,
        source: str = "user_taught",
        user_id: str = "default_user",
        dependencies: List[str] = None
    ) -> Optional[str]:
        """
        Add a formula to Atom's memory.

        Args:
            expression: The formula expression (e.g., "Revenue - Cost")
            name: Human-readable name (e.g., "Net Profit")
            domain: Category (e.g., "finance", "sales", "operations")
            use_case: Description of when to use this formula
            parameters: List of parameter definitions [{"name": "Revenue", "type": "number"}]
            example_input: Example input values
            example_output: Expected output for the example
            source: Origin ("excel", "user_taught", "template")
            user_id: Owner of the formula
            dependencies: List of formula IDs this formula depends on

        Returns:
            formula_id if successful, None otherwise
        """
        self._ensure_initialized()

        if not self._lancedb:
            logger.error("Cannot add formula: LanceDB not available")
            return None

        formula_id = str(uuid.uuid4())

        # Create searchable text for embedding
        searchable_text = f"{name}. {use_case}. Domain: {domain}. Expression: {expression}"

        # Prepare metadata
        metadata = {
            "expression": expression,
            "name": name,
            "domain": domain,
            "parameters": json.dumps(parameters or []),
            "example_input": json.dumps(example_input or {}),
            "example_output": json.dumps(example_output) if example_output else "",
            "source": source,
            "dependencies": json.dumps(dependencies or []),
            "created_at": datetime.utcnow().isoformat()
        }

        try:
            # Store in LanceDB with embedding
            success = self._lancedb.add_document(
                table_name=FORMULAS_TABLE,
                text=searchable_text,
                source=f"formula:{source}",
                metadata=metadata,
                user_id=user_id,
                extract_knowledge=False  # Don't extract entities from formulas
            )

            if success:
                logger.info(f"Formula added: {name} ({formula_id})")

                # Add dependency edges to GraphRAG
                if dependencies and self._graphrag:
                    for dep_id in dependencies:
                        self._add_dependency_edge(formula_id, dep_id)

                return formula_id

            return None

        except Exception as e:
            logger.error(f"Failed to add formula: {e}")
            return None

    def _add_dependency_edge(self, formula_id: str, depends_on_id: str):
        """Add a DEPENDS_ON edge in the knowledge graph."""
        if not self._graphrag:
            return

        try:
            # Use LanceDB to add edge (knowledge graph is stored there)
            if self._lancedb:
                self._lancedb.add_knowledge_edge(
                    from_id=formula_id,
                    to_id=depends_on_id,
                    rel_type="DEPENDS_ON",
                    description=f"Formula {formula_id} depends on {depends_on_id}",
                    metadata={"edge_type": "formula_dependency"}
                )
        except Exception as e:
            logger.warning(f"Failed to add dependency edge: {e}")

    def search_formulas(
        self,
        query: str,
        domain: Optional[str] = None,
        limit: int = 10,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for formulas by natural language query.

        Args:
            query: Natural language description (e.g., "calculate profit margin")
            domain: Optional domain filter (e.g., "finance")
            limit: Maximum results to return
            user_id: Optional user filter

        Returns:
            List of matching formulas with scores
        """
        self._ensure_initialized()

        if not self._lancedb:
            logger.warning("Cannot search formulas: LanceDB not available")
            return []

        try:
            # Build filter string
            filter_parts = []
            if domain:
                filter_parts.append(f"metadata LIKE '%\"domain\": \"{domain}\"%'")
            filter_str = " AND ".join(filter_parts) if filter_parts else None

            # Semantic search
            results = self._lancedb.search(
                table_name=FORMULAS_TABLE,
                query=query,
                user_id=user_id,
                limit=limit,
                filter_str=filter_str
            )

            # Parse results
            formulas = []
            for result in results:
                try:
                    metadata = json.loads(result.get("metadata", "{}"))
                    formulas.append({
                        "id": result.get("id"),
                        "expression": metadata.get("expression", ""),
                        "name": metadata.get("name", ""),
                        "domain": metadata.get("domain", ""),
                        "use_case": result.get("text", ""),
                        "parameters": json.loads(metadata.get("parameters", "[]")),
                        "source": metadata.get("source", ""),
                        "score": result.get("_distance", 0),
                        "created_at": metadata.get("created_at")
                    })
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse formula result: {e}")
                    continue

            return formulas

        except Exception as e:
            logger.error(f"Formula search failed: {e}")
            return []

    def get_formula(self, formula_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific formula by ID."""
        self._ensure_initialized()

        if not self._lancedb:
            return None

        try:
            results = self._lancedb.search(
                table_name=FORMULAS_TABLE,
                query="",  # Empty query to get by ID
                filter_str=f"id = '{formula_id}'",
                limit=1
            )

            if results:
                result = results[0]
                metadata = json.loads(result.get("metadata", "{}"))
                return {
                    "id": result.get("id"),
                    "expression": metadata.get("expression", ""),
                    "name": metadata.get("name", ""),
                    "domain": metadata.get("domain", ""),
                    "use_case": result.get("text", ""),
                    "parameters": json.loads(metadata.get("parameters", "[]")),
                    "example_input": json.loads(metadata.get("example_input", "{}")),
                    "example_output": json.loads(metadata.get("example_output", "null")),
                    "source": metadata.get("source", ""),
                    "dependencies": json.loads(metadata.get("dependencies", "[]")),
                    "created_at": metadata.get("created_at")
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get formula {formula_id}: {e}")
            return None

    def get_formula_lineage(self, formula_id: str) -> Dict[str, Any]:
        """
        Get the dependency lineage for a formula.

        Returns:
            Dict with 'upstream' (formulas this depends on) and 
            'downstream' (formulas that depend on this)
        """
        self._ensure_initialized()

        lineage = {
            "formula_id": formula_id,
            "upstream": [],
            "downstream": []
        }

        if not self._lancedb:
            return lineage

        try:
            # Query knowledge graph for edges
            edges = self._lancedb.query_knowledge_graph(
                query=f"formula dependency {formula_id}",
                limit=50
            )

            for edge in edges:
                if edge.get("from_id") == formula_id:
                    lineage["upstream"].append({
                        "formula_id": edge.get("to_id"),
                        "relationship": edge.get("rel_type")
                    })
                elif edge.get("to_id") == formula_id:
                    lineage["downstream"].append({
                        "formula_id": edge.get("from_id"),
                        "relationship": edge.get("rel_type")
                    })

            return lineage

        except Exception as e:
            logger.error(f"Failed to get lineage for {formula_id}: {e}")
            return lineage

    def apply_formula(
        self,
        formula_id: str,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a formula with given inputs.

        Args:
            formula_id: ID of the formula to apply
            inputs: Dictionary of parameter values

        Returns:
            Dict with 'success', 'result', and optional 'error'
        """
        formula = self.get_formula(formula_id)

        if not formula:
            return {"success": False, "error": f"Formula {formula_id} not found"}

        expression = formula.get("expression", "")
        parameters = formula.get("parameters", [])

        # Validate inputs
        for param in parameters:
            param_name = param.get("name")
            if param_name not in inputs:
                return {
                    "success": False,
                    "error": f"Missing required parameter: {param_name}"
                }

        try:
            # Safe evaluation using Python's eval with restricted globals
            # In production, use a proper expression parser
            safe_globals = {"__builtins__": {}}
            safe_locals = {**inputs}

            # Add common math functions
            import math
            safe_globals.update({
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "sqrt": math.sqrt,
                "pow": pow
            })

            result = eval(expression, safe_globals, safe_locals)

            return {
                "success": True,
                "result": result,
                "formula_name": formula.get("name"),
                "expression": expression,
                "inputs": inputs
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Evaluation failed: {str(e)}",
                "expression": expression,
                "inputs": inputs
            }

    def delete_formula(self, formula_id: str) -> bool:
        """Delete a formula from memory."""
        self._ensure_initialized()

        if not self._lancedb:
            return False

        try:
            table = self._lancedb.get_table(FORMULAS_TABLE)
            if table:
                table.delete(f"id = '{formula_id}'")
                logger.info(f"Formula deleted: {formula_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to delete formula {formula_id}: {e}")
            return False


# Singleton instance
_formula_manager: Optional[FormulaMemoryManager] = None


def get_formula_manager(workspace_id: str = "default") -> FormulaMemoryManager:
    """Get or create the formula memory manager instance."""
    global _formula_manager
    if _formula_manager is None or _formula_manager.workspace_id != workspace_id:
        _formula_manager = FormulaMemoryManager(workspace_id)
    return _formula_manager
