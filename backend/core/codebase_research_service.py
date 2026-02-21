"""
Codebase Research Service for Autonomous Coding Agents

Provides comprehensive codebase analysis capabilities:
- AST parsing for pattern detection
- Embedding-based similarity search
- Import graph analysis with cycle detection
- API catalog generation
- Conflict detection before code generation

Purpose: Enable autonomous agents to understand existing codebase patterns,
avoid duplication, identify integration points, and ensure compatibility.

Usage:
    service = CodebaseResearchService(db)
    results = await service.analyze_codebase(requirements, workspace_id)
"""

import ast
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from sqlalchemy.orm import Session

# Import existing services
try:
    from core.embedding_service import EmbeddingService
    from core.lancedb_handler import LanceDBHandler
    from core.requirement_parser_service import ParsedRequirement
except ImportError:
    # Create placeholder if not yet implemented
    ParsedRequirement = Dict[str, Any]

logger = logging.getLogger(__name__)


# ============================================================================
# Task 1: AST Parsing Utilities
# ============================================================================

class ASTParser:
    """
    AST-based code analysis utilities.

    Extracts functions, classes, imports, and API routes from Python files
    using Python's built-in ast module. No external dependencies required.

    Attributes:
        codebase_root: Root directory for codebase analysis (default: "backend")

    Example:
        parser = ASTParser("backend")
        functions = parser.extract_functions("backend/api/auth_routes.py")
        classes = parser.extract_classes("backend/core/models.py")
    """

    def __init__(self, codebase_root: str = "backend"):
        """
        Initialize AST parser.

        Args:
            codebase_root: Root directory of codebase to analyze
        """
        self.codebase_root = Path(codebase_root)

    def parse_file(self, file_path: str) -> Optional[ast.AST]:
        """
        Parse Python file into AST.

        Handles parse errors gracefully by returning None.

        Args:
            file_path: Path to Python file (relative or absolute)

        Returns:
            AST tree or None if parsing fails
        """
        try:
            # Convert to absolute path if relative
            path = Path(file_path)
            if not path.is_absolute():
                path = self.codebase_root / path

            with open(path, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=str(path))
            return tree

        except SyntaxError as e:
            logger.warning(f"Syntax error parsing {file_path}: {e}")
            return None
        except FileNotFoundError:
            logger.warning(f"File not found: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return None

    def extract_functions(
        self,
        file_path: str
    ) -> List[Dict[str, Any]]:
        """
        Extract all functions with signatures and docstrings.

        Returns:
            List of function dictionaries with keys:
                - name: Function name
                - args: List of argument names
                - returns: Return type annotation (if any)
                - docstring: Function docstring
                - lineno: Line number
                - is_async: Whether function is async
        """
        tree = self.parse_file(file_path)
        if tree is None:
            return []

        functions = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = {
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "returns": ast.unparse(node.returns) if node.returns else None,
                    "docstring": ast.get_docstring(node),
                    "lineno": node.lineno,
                    "is_async": isinstance(node, ast.AsyncFunctionDef)
                }
                functions.append(func_info)

        return functions

    def extract_classes(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract all classes with methods and bases.

        Returns:
            List of class dictionaries with keys:
                - name: Class name
                - bases: List of base class names
                - methods: List of method names
                - docstring: Class docstring
                - lineno: Line number
        """
        tree = self.parse_file(file_path)
        if tree is None:
            return []

        classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Extract base class names
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(ast.unparse(base))

                # Extract method names
                methods = [
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]

                class_info = {
                    "name": node.name,
                    "bases": bases,
                    "methods": methods,
                    "docstring": ast.get_docstring(node),
                    "lineno": node.lineno
                }
                classes.append(class_info)

        return classes

    def extract_imports(self, file_path: str) -> Dict[str, List[str]]:
        """
        Extract import statements.

        Returns:
            Dictionary with keys:
                - from_imports: List of "from X import Y" statements
                - direct_imports: List of "import X" statements
        """
        tree = self.parse_file(file_path)
        if tree is None:
            return {"from_imports": [], "direct_imports": []}

        from_imports = []
        direct_imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [n.name for n in node.names]
                for name in names:
                    from_imports.append(f"from {module} import {name}")

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    direct_imports.append(f"import {alias.name}")

        return {
            "from_imports": from_imports,
            "direct_imports": direct_imports
        }

    def find_api_routes(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract FastAPI route definitions.

        Looks for function decorators like @router.get, @app.post, etc.

        Returns:
            List of route dictionaries with keys:
                - path: Route path (e.g., "/api/auth/login")
                - method: HTTP method (GET, POST, etc.)
                - function: Handler function name
                - lineno: Line number
        """
        tree = self.parse_file(file_path)
        if tree is None:
            return []

        routes = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check for route decorators
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        # @router.get("/path")
                        if isinstance(decorator.func, ast.Attribute):
                            method = decorator.func.attr.upper()
                            # Extract path from first argument
                            if decorator.args:
                                path_arg = decorator.args[0]
                                if isinstance(path_arg, ast.Constant):
                                    path = path_arg.value
                                elif isinstance(path_arg, ast.Str):  # Python < 3.8
                                    path = path_arg.s
                                else:
                                    path = ast.unparse(path_arg)

                                routes.append({
                                    "path": path,
                                    "method": method,
                                    "function": node.name,
                                    "lineno": node.lineno
                                })

        return routes

    def extract_dependencies(self, file_path: str) -> Set[str]:
        """
        Extract module dependencies from imports.

        Returns:
            Set of module names (e.g., {"sqlalchemy", "fastapi", "core.models"})
        """
        imports = self.extract_imports(file_path)
        dependencies = set()

        # Parse direct imports
        for imp in imports["direct_imports"]:
            module = imp.replace("import ", "").split(".")[0].strip()
            dependencies.add(module)

        # Parse from imports
        for imp in imports["from_imports"]:
            if imp.startswith("from "):
                module = imp[5:].split(" import")[0].split(".")[0].strip()
                dependencies.add(module)

        return dependencies


# ============================================================================
# Task 3: Import Graph Analysis
# ============================================================================

class ImportGraphAnalyzer:
    """
    Analyze import dependencies between modules.

    Builds dependency graph, detects circular imports, estimates impact
    of changes, and determines execution order for testing.

    Attributes:
        codebase_root: Root directory for analysis
        graph: Adjacency list {module: [dependencies]}

    Example:
        analyzer = ImportGraphAnalyzer("backend")
        graph = analyzer.build_graph()
        cycles = analyzer.detect_cycles()
    """

    def __init__(self, codebase_root: str = "backend"):
        """
        Initialize import graph analyzer.

        Args:
            codebase_root: Root directory of codebase
        """
        self.codebase_root = Path(codebase_root)
        self.graph: Dict[str, Set[str]] = {}

    def build_graph(self) -> Dict[str, Set[str]]:
        """
        Build dependency graph: {module: [dependencies]}.

        Walks through all Python files, extracts imports using AST,
        and builds adjacency list representation.

        Returns:
            Dictionary mapping module names to their dependencies
        """
        self.graph = {}

        # Find all Python files
        py_files = list(self.codebase_root.rglob("*.py"))

        for file_path in py_files:
            # Determine module name (relative to codebase_root)
            rel_path = file_path.relative_to(self.codebase_root)
            module = str(rel_path.with_suffix('')).replace(os.sep, '.')

            # Parse imports
            parser = ASTParser(str(self.codebase_root))
            dependencies = parser.extract_dependencies(str(file_path))

            # Filter to local imports only (from core.xxx, from api.xxx)
            local_deps = set()
            for dep in dependencies:
                if dep.startswith(('core.', 'api.', 'tools.', 'integrations.')):
                    local_deps.add(dep)

            self.graph[module] = local_deps

        return self.graph

    def find_dependents(self, module_name: str) -> List[str]:
        """
        Find all modules that import the given module.

        Reverse dependency lookup - useful for impact analysis.

        Args:
            module_name: Module to find dependents for

        Returns:
            List of module names that depend on the given module
        """
        if not self.graph:
            self.build_graph()

        dependents = []
        for module, deps in self.graph.items():
            if module_name in deps:
                dependents.append(module)

        return dependents

    def detect_cycles(self) -> List[List[str]]:
        """
        Detect circular import dependencies using DFS.

        Returns:
            List of cycles (each cycle is a list of module names)
        """
        if not self.graph:
            self.build_graph()

        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.graph.get(node, set()):
                if neighbor not in visited:
                    result = dfs(neighbor, path)
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # Found cycle - extract it from path
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    return cycle

            path.pop()
            rec_stack.remove(node)
            return None

        for node in self.graph:
            if node not in visited:
                result = dfs(node, [])
                if result:
                    cycles.append(result)

        return cycles

    def get_execution_order(
        self,
        changed_modules: Set[str]
    ) -> List[str]:
        """
        Get topological order for testing affected modules.

        Returns modules in dependency order (leaves first).

        Args:
            changed_modules: Set of modules that were modified

        Returns:
            List of modules in testing order (dependencies first)
        """
        if not self.graph:
            self.build_graph()

        # Build subgraph of affected modules
        affected = set(changed_modules)
        for module in changed_modules:
            affected.update(self.find_dependents(module))

        # Topological sort (Kahn's algorithm)
        in_degree = {m: 0 for m in affected}
        for module in affected:
            for dep in self.graph.get(module, set()):
                if dep in affected:
                    in_degree[module] += 1

        # Queue of nodes with no incoming edges
        queue = [m for m, degree in in_degree.items() if degree == 0]
        order = []

        while queue:
            module = queue.pop(0)
            order.append(module)

            for dependent in self.find_dependents(module):
                if dependent in affected:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return order

    def estimate_impact(
        self,
        files_to_modify: List[str]
    ) -> Dict[str, Any]:
        """
        Estimate impact of file modifications.

        Args:
            files_to_modify: List of file paths to be modified

        Returns:
            Dictionary with keys:
                - directly_affected: Modules directly imported
                - indirectly_affected: Transitively affected modules
                - risk_level: "low", "medium", or "high"
        """
        if not self.graph:
            self.build_graph()

        # Convert file paths to module names
        modified_modules = set()
        for file_path in files_to_modify:
            path = Path(file_path)
            if path.is_absolute():
                path = path.relative_to(self.codebase_root)
            module = str(path.with_suffix('')).replace(os.sep, '.')
            modified_modules.add(module)

        # Find directly affected (importers of modified modules)
        directly_affected = set()
        for module in modified_modules:
            directly_affected.update(self.find_dependents(module))

        # Find indirectly affected (transitive closure)
        indirectly_affected = set()
        queue = list(directly_affected)

        while queue:
            module = queue.pop(0)
            for dependent in self.find_dependents(module):
                if dependent not in indirectly_affected:
                    indirectly_affected.add(dependent)
                    queue.append(dependent)

        # Calculate risk level
        total_affected = len(directly_affected) + len(indirectly_affected)
        if total_affected == 0:
            risk_level = "low"
        elif total_affected < 5:
            risk_level = "low"
        elif total_affected < 15:
            risk_level = "medium"
        else:
            risk_level = "high"

        return {
            "directly_affected": list(directly_affected),
            "indirectly_affected": list(indirectly_affected),
            "risk_level": risk_level
        }


# ============================================================================
# Task 4: API Catalog Generator
# ============================================================================

class APICatalogGenerator:
    """
    Generate catalog of existing API endpoints.

    Scans backend/api/ directory for FastAPI routes and generates
    comprehensive catalog with metadata for conflict detection and
    integration planning.

    Attributes:
        codebase_root: Root directory for analysis
        ast_parser: ASTParser instance

    Example:
        catalog = APICatalogGenerator()
        endpoints = catalog.generate_catalog()
    """

    def __init__(self, codebase_root: str = "backend"):
        """
        Initialize API catalog generator.

        Args:
            codebase_root: Root directory of codebase
        """
        self.codebase_root = Path(codebase_root)
        self.ast_parser = ASTParser(codebase_root)

    def generate_catalog(self) -> Dict[str, Any]:
        """
        Scan all API route files and generate endpoint catalog.

        Returns:
            Dictionary with keys:
                - endpoints: List of endpoint dictionaries
                - routers: List of router names
                - namespaces: Dict mapping namespace to route count
        """
        api_dir = self.codebase_root / "api"

        if not api_dir.exists():
            logger.warning(f"API directory not found: {api_dir}")
            return {"endpoints": [], "routers": [], "namespaces": {}}

        endpoints = []
        routers = set()
        namespaces = {}

        # Scan all Python files in api/
        for route_file in api_dir.glob("*_routes.py"):
            routes = self.ast_parser.find_api_routes(str(route_file))

            for route in routes:
                # Extract namespace from path
                namespace = "/".join(route["path"].split("/")[:2]) if route["path"] else "/"

                # Enrich endpoint info
                endpoint = {
                    "path": route["path"],
                    "method": route["method"],
                    "file": str(route_file.relative_to(self.codebase_root)),
                    "function": route["function"],
                    "lineno": route["lineno"],
                    "namespace": namespace
                }
                endpoints.append(endpoint)

                # Track namespaces
                namespaces[namespace] = namespaces.get(namespace, 0) + 1

            # Track router names
            router_name = route_file.stem.replace("_routes", "")
            routers.add(router_name)

        return {
            "endpoints": endpoints,
            "routers": sorted(list(routers)),
            "namespaces": namespaces
        }

    def find_available_namespaces(self) -> List[str]:
        """
        Find available API namespaces for new routes.

        Returns namespaces with <10 routes (opportunity for extension).

        Returns:
            List of namespace paths with capacity
        """
        catalog = self.generate_catalog()
        available = []

        for namespace, count in catalog["namespaces"].items():
            if count < 10:
                available.append(namespace)

        return sorted(available)

    def detect_route_conflicts(
        self,
        proposed_path: str,
        proposed_method: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if proposed route conflicts with existing route.

        Args:
            proposed_path: Proposed route path (e.g., "/api/auth/login")
            proposed_method: Proposed HTTP method (GET, POST, etc.)

        Returns:
            Conflict details dictionary or None if no conflict
        """
        catalog = self.generate_catalog()

        for endpoint in catalog["endpoints"]:
            # Check for exact match
            if endpoint["path"] == proposed_path and endpoint["method"] == proposed_method.upper():
                return {
                    "type": "exact_match",
                    "severity": "critical",
                    "existing_file": endpoint["file"],
                    "existing_function": endpoint["function"],
                    "description": f"Route {proposed_method} {proposed_path} already exists in {endpoint['file']}"
                }

            # Check for path collision (same path, different method)
            if endpoint["path"] == proposed_path:
                return {
                    "type": "path_collision",
                    "severity": "warning",
                    "existing_method": endpoint["method"],
                    "existing_file": endpoint["file"],
                    "description": f"Path {proposed_path} exists with {endpoint['method']} method"
                }

        return None


# ============================================================================
# Task 5: Conflict Detection
# ============================================================================

class ConflictDetector:
    """
    Detect potential conflicts before code generation.

    Checks for duplicate features, breaking changes, model conflicts,
    and route collisions to prevent implementation issues.

    Attributes:
        ast_parser: ASTParser instance
        import_analyzer: ImportGraphAnalyzer instance
        api_catalog: APICatalogGenerator instance

    Example:
        detector = ConflictDetector(ast_parser, import_analyzer, api_catalog)
        conflicts = await detector.detect_conflicts(requirements)
    """

    def __init__(
        self,
        ast_parser: ASTParser,
        import_analyzer: ImportGraphAnalyzer,
        api_catalog: APICatalogGenerator
    ):
        """
        Initialize conflict detector.

        Args:
            ast_parser: AST parser for code analysis
            import_analyzer: Import graph analyzer
            api_catalog: API catalog generator
        """
        self.ast_parser = ast_parser
        self.import_analyzer = import_analyzer
        self.api_catalog = api_catalog

    async def detect_conflicts(
        self,
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze requirements and detect all potential conflicts.

        Args:
            requirements: Parsed requirements from RequirementParserService

        Returns:
            Dictionary with keys:
                - conflicts: List of conflict dictionaries
                - warnings: List of warning dictionaries
                - safe_to_proceed: Boolean indicating if safe to implement
        """
        conflicts = []
        warnings = []

        # Check for duplicate features
        feature_desc = requirements.get("feature_description", "")
        duplicates = self.detect_duplicate_features(feature_desc)
        conflicts.extend(duplicates)

        # Check for breaking changes
        files_to_modify = requirements.get("files_to_modify", [])
        breaking_changes = self.detect_breaking_changes(files_to_modify)
        conflicts.extend(breaking_changes)

        # Check for model conflicts
        proposed_models = requirements.get("models", [])
        model_conflicts = self.detect_model_conflicts(proposed_models)
        conflicts.extend(model_conflicts)

        # Check API routes
        proposed_routes = requirements.get("api_routes", [])
        for route in proposed_routes:
            conflict = self.api_catalog.detect_route_conflicts(
                route.get("path", ""),
                route.get("method", "GET")
            )
            if conflict:
                conflicts.append(conflict)

        # Determine if safe to proceed
        critical_conflicts = [c for c in conflicts if c.get("severity") == "critical"]
        safe_to_proceed = len(critical_conflicts) == 0

        return {
            "conflicts": conflicts,
            "warnings": warnings,
            "safe_to_proceed": safe_to_proceed
        }

    def detect_duplicate_features(
        self,
        feature_description: str
    ) -> List[Dict[str, Any]]:
        """
        Check if feature already exists using similarity search.

        This is a placeholder - actual implementation would use
        embedding search via CodebaseResearchService.

        Args:
            feature_description: Description of proposed feature

        Returns:
            List of duplicate conflict dictionaries
        """
        # TODO: Implement with embedding search in Task 2
        return []

    def detect_breaking_changes(
        self,
        files_to_modify: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Analyze proposed changes for breaking changes.

        Checks: removed APIs, renamed models, deleted functions.

        Args:
            files_to_modify: List of files with proposed changes

        Returns:
            List of breaking change conflict dictionaries
        """
        breaking_changes = []

        for file_info in files_to_modify:
            file_path = file_info.get("path", "")
            action = file_info.get("action", "")  # "create", "modify", "delete"

            if action == "delete":
                # Check for breaking changes before deletion
                functions = self.ast_parser.extract_functions(file_path)
                classes = self.ast_parser.extract_classes(file_path)
                routes = self.ast_parser.find_api_routes(file_path)

                # Check if file has public APIs
                if routes:
                    breaking_changes.append({
                        "type": "breaking_change",
                        "severity": "critical",
                        "description": f"Deleting {file_path} will remove {len(routes)} API routes",
                        "existing_file": file_path,
                        "suggestion": "Migrate routes before deletion"
                    })

                # Check for dependents
                module = file_path.replace(".py", "").replace(os.sep, ".")
                dependents = self.import_analyzer.find_dependents(module)
                if dependents:
                    breaking_changes.append({
                        "type": "breaking_change",
                        "severity": "high",
                        "description": f"Deleting {file_path} breaks {len(dependents)} dependent modules",
                        "dependents": dependents,
                        "suggestion": "Update dependents before deletion"
                    })

        return breaking_changes

    def detect_model_conflicts(
        self,
        proposed_models: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Check for SQLAlchemy model conflicts.

        Checks: duplicate table names, conflicting foreign keys.

        Args:
            proposed_models: List of model definitions

        Returns:
            List of model conflict dictionaries
        """
        # TODO: Parse existing models from backend/core/models.py
        # and check for table name conflicts
        return []


# ============================================================================
# Task 2 & 6: Main CodebaseResearchService
# ============================================================================

class CodebaseResearchService:
    """
    Main service for codebase research and analysis.

    Orchestrates all research components:
    - AST parsing for code structure
    - Embedding search for similar features
    - Import graph analysis for dependencies
    - API catalog for integration points
    - Conflict detection for safety

    Attributes:
        db: SQLAlchemy database session
        embedding_service: EmbeddingService for similarity search
        lancedb: LanceDB handler for vector storage
        ast_parser: ASTParser instance
        import_analyzer: ImportGraphAnalyzer instance
        api_catalog: APICatalogGenerator instance
        conflict_detector: ConflictDetector instance

    Example:
        service = CodebaseResearchService(db)
        results = await service.analyze_codebase(requirements, "default")
    """

    def __init__(
        self,
        db: Session,
        embedding_service: Optional['EmbeddingService'] = None,
        lancedb: Optional['LanceDBHandler'] = None
    ):
        """
        Initialize codebase research service.

        Args:
            db: SQLAlchemy database session
            embedding_service: Optional embedding service (created if None)
            lancedb: Optional LanceDB handler (created if None)
        """
        self.db = db

        # Initialize services
        if embedding_service is None:
            try:
                from core.embedding_service import EmbeddingService
                self.embedding_service = EmbeddingService()
            except ImportError:
                self.embedding_service = None
                logger.warning("EmbeddingService not available, similarity search disabled")
        else:
            self.embedding_service = embedding_service

        if lancedb is None:
            try:
                from core.lancedb_handler import get_lancedb_handler
                self.lancedb = get_lancedb_handler()
            except ImportError:
                self.lancedb = None
                logger.warning("LanceDB handler not available, vector search disabled")
        else:
            self.lancedb = lancedb

        # Initialize components
        self.ast_parser = ASTParser()
        self.import_analyzer = ImportGraphAnalyzer()
        self.api_catalog = APICatalogGenerator()
        self.conflict_detector = ConflictDetector(
            self.ast_parser,
            self.import_analyzer,
            self.api_catalog
        )

        # In-memory cache for search results
        self._search_cache: Dict[str, List[Dict[str, Any]]] = {}

    async def analyze_codebase(
        self,
        requirements: Dict[str, Any],
        workspace_id: str
    ) -> Dict[str, Any]:
        """
        Perform comprehensive codebase analysis.

        Args:
            requirements: Parsed requirements from RequirementParserService
            workspace_id: Workspace context

        Returns:
            Dictionary with keys:
                - similar_features: List of similar existing features
                - integration_points: List of files needing modification
                - conflicts: List of detected conflicts
                - import_graph: Dependency graph information
                - api_catalog: API endpoint catalog
                - recommendations: Implementation recommendations
        """
        logger.info(f"Starting codebase analysis for workspace: {workspace_id}")

        # 1. Find similar features using embedding search
        feature_desc = requirements.get("feature_description", "")
        user_stories = requirements.get("user_stories", [])

        similar_features = await self.find_similar_features(
            feature_desc,
            top_k=5
        )

        # 2. Identify integration points
        integration_points = self.get_integration_points(user_stories)

        # 3. Detect conflicts
        conflict_result = await self.conflict_detector.detect_conflicts(requirements)

        # 4. Generate import graph info
        import_graph = {
            "graph": self.import_analyzer.build_graph(),
            "cycles": self.import_analyzer.detect_cycles()
        }

        # 5. Get API catalog
        api_catalog = self.api_catalog.generate_catalog()

        # 6. Generate recommendations
        recommendations = self.generate_recommendations(
            similar_features,
            conflict_result["conflicts"],
            integration_points
        )

        return {
            "similar_features": similar_features,
            "integration_points": integration_points,
            "conflicts": conflict_result["conflicts"],
            "warnings": conflict_result["warnings"],
            "safe_to_proceed": conflict_result["safe_to_proceed"],
            "import_graph": import_graph,
            "api_catalog": api_catalog,
            "recommendations": recommendations
        }

    async def index_codebase(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Index all Python files in codebase for similarity search.

        Walks backend/ directory, extracts functions/classes,
        generates embeddings, stores in LanceDB.

        Args:
            force_refresh: Re-index even if already indexed

        Returns:
            Dictionary with keys:
                - indexed: Number of files indexed
                - errors: Number of errors encountered
                - duration_seconds: Time taken to index
        """
        import time
        start_time = time.time()

        if self.embedding_service is None:
            logger.error("Cannot index: EmbeddingService not available")
            return {"indexed": 0, "errors": 1, "duration_seconds": 0}

        indexed = 0
        errors = 0

        # Find all Python files
        codebase_path = Path(self.ast_parser.codebase_root)
        py_files = list(codebase_path.rglob("*.py"))

        logger.info(f"Indexing {len(py_files)} Python files...")

        for file_path in py_files:
            try:
                # Extract functions and classes
                functions = self.ast_parser.extract_functions(str(file_path))
                classes = self.ast_parser.extract_classes(str(file_path))

                # Generate embeddings for functions
                for func in functions:
                    # Combine signature and docstring for embedding
                    text = f"{func['name']}({', '.join(func['args'])})"
                    if func['docstring']:
                        text += f"\n{func['docstring']}"

                    # Generate embedding
                    embedding = await self.embedding_service.generate_embedding(text)

                    # Store in LanceDB (if available)
                    if self.lancedb:
                        # TODO: Create code_embeddings table
                        pass

                indexed += 1

            except Exception as e:
                logger.error(f"Failed to index {file_path}: {e}")
                errors += 1

        duration = time.time() - start_time

        logger.info(f"Indexing complete: {indexed} files, {errors} errors, {duration:.2f}s")

        return {
            "indexed": indexed,
            "errors": errors,
            "duration_seconds": duration
        }

    async def find_similar_features(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find similar code features using embedding search.

        Args:
            query: Natural language description or code snippet
            top_k: Maximum number of results
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of feature dictionaries with keys:
                - file: File path
                - name: Function or class name
                - type: "function" or "class"
                - similarity: Similarity score
                - preview: Code preview
                - line: Line number
        """
        # Check cache
        cache_key = f"{query}:{top_k}:{min_similarity}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        results = []

        if self.embedding_service is None:
            logger.warning("Embedding search unavailable, using keyword fallback")
            return self._search_by_keywords([query])

        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query)

            # Search LanceDB (if available)
            if self.lancedb:
                # TODO: Implement vector search in code_embeddings table
                pass

            # Fallback: keyword search
            results = self._search_by_keywords([query])

        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            results = self._search_by_keywords([query])

        # Filter by similarity and limit
        filtered = [
            r for r in results
            if r.get("similarity", 0) >= min_similarity
        ][:top_k]

        # Cache results
        self._search_cache[cache_key] = filtered

        return filtered

    def _search_by_keywords(
        self,
        keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fallback: search files by keyword matching.

        Args:
            keywords: List of keywords to search for

        Returns:
            List of feature dictionaries with similarity scores
        """
        results = []
        codebase_path = Path(self.ast_parser.codebase_root)

        for file_path in codebase_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for keyword matches
                matches = 0
                for keyword in keywords:
                    if keyword.lower() in content.lower():
                        matches += 1

                if matches > 0:
                    # Calculate similarity based on match count
                    similarity = min(matches / len(keywords), 1.0)

                    results.append({
                        "file": str(file_path.relative_to(codebase_path)),
                        "name": file_path.stem,
                        "type": "file",
                        "similarity": similarity,
                        "preview": content[:200],
                        "line": 1
                    })

            except Exception as e:
                logger.debug(f"Failed to search {file_path}: {e}")

        # Sort by similarity descending
        results.sort(key=lambda x: x["similarity"], reverse=True)

        return results

    def get_integration_points(
        self,
        user_stories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Identify files that need modification for integration.

        Args:
            user_stories: List of user story dictionaries

        Returns:
            List of integration point dictionaries with keys:
                - file: File path
                - reason: Reason for modification
                - type: "api", "model", "service", or "frontend"
        """
        integration_points = []

        # Analyze user stories for integration clues
        for story in user_stories:
            action = story.get("action", "").lower()
            value = story.get("value", "").lower()

            # API endpoints
            if any(keyword in action for keyword in ["endpoint", "route", "api", "http"]):
                available_namespaces = self.api_catalog.find_available_namespaces()
                if available_namespaces:
                    integration_points.append({
                        "file": f"backend/api/{available_namespaces[0].strip('/')}s_routes.py",
                        "reason": "Add new API endpoint",
                        "type": "api"
                    })

            # Database models
            if any(keyword in action for keyword in ["model", "table", "database", "store"]):
                integration_points.append({
                    "file": "backend/core/models.py",
                    "reason": "Add database model",
                    "type": "model"
                })

            # Services
            if any(keyword in action for keyword in ["service", "business logic", "process"]):
                integration_points.append({
                    "file": "backend/core/",
                    "reason": "Add service layer",
                    "type": "service"
                })

        # Remove duplicates
        seen = set()
        unique_points = []
        for point in integration_points:
            key = (point["file"], point["type"])
            if key not in seen:
                seen.add(key)
                unique_points.append(point)

        return unique_points

    def generate_recommendations(
        self,
        similar_features: List[Dict],
        conflicts: List[Dict],
        integration_points: List[Dict]
    ) -> List[str]:
        """
        Generate implementation recommendations based on analysis.

        Args:
            similar_features: List of similar existing features
            conflicts: List of detected conflicts
            integration_points: List of integration points

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Check for similar features to reuse
        if similar_features:
            top_feature = similar_features[0]
            if top_feature.get("similarity", 0) > 0.8:
                recommendations.append(
                    f"Highly similar feature found: {top_feature['name']} "
                    f"in {top_feature['file']} ({top_feature['similarity']:.0%} match). "
                    f"Consider reusing or extending this implementation."
                )
            elif len(similar_features) > 0:
                recommendations.append(
                    f"Found {len(similar_features)} similar features. "
                    f"Review existing patterns before implementing."
                )

        # Check for conflicts
        critical_conflicts = [c for c in conflicts if c.get("severity") == "critical"]
        if critical_conflicts:
            recommendations.append(
                f"CRITICAL: {len(critical_conflicts)} blocking conflicts detected. "
                f"Resolution required before implementation."
            )

        # Integration recommendations
        if integration_points:
            api_points = [p for p in integration_points if p["type"] == "api"]
            if api_points:
                recommendations.append(
                    f"API integration: {len(api_points)} endpoints to add. "
                    f"Use existing FastAPI router patterns."
                )

            model_points = [p for p in integration_points if p["type"] == "model"]
            if model_points:
                recommendations.append(
                    f"Database changes required. Create Alembic migration "
                    f"before modifying models.py."
                )

        # Best practices
        recommendations.append("Follow Atom governance patterns for all new code.")
        recommendations.append("Add comprehensive tests (target: 85% coverage).")
        recommendations.append("Use type hints and Google-style docstrings.")

        return recommendations


# ============================================================================
# Convenience Functions
# ============================================================================

def get_codebase_research_service(
    db: Session
) -> CodebaseResearchService:
    """
    Get or create CodebaseResearchService instance.

    Args:
        db: SQLAlchemy database session

    Returns:
        CodebaseResearchService instance
    """
    return CodebaseResearchService(db)


async def analyze_codebase(
    requirements: Dict[str, Any],
    workspace_id: str = "default",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Convenience function for codebase analysis.

    Args:
        requirements: Parsed requirements
        workspace_id: Workspace identifier
        db: Optional database session (created if None)

    Returns:
        Analysis results dictionary
    """
    if db is None:
        from core.database import SessionLocal
        db = SessionLocal()

    service = get_codebase_research_service(db)
    return await service.analyze_codebase(requirements, workspace_id)
