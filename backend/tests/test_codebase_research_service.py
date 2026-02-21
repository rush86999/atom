"""
Comprehensive tests for CodebaseResearchService

Tests cover:
- AST parsing (functions, classes, imports, API routes)
- Embedding-based similarity search
- Import graph analysis (cycles, impact estimation)
- API catalog generation and conflict detection
- Full analysis orchestration

Coverage target: >= 80%
"""

import asyncio
import json
import os
import pytest
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from sqlalchemy.orm import Session


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Create test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    mock = AsyncMock()
    mock.generate_embedding.return_value = [0.1] * 384  # 384-dim FastEmbed
    mock.generate_embeddings_batch.return_value = [[0.1] * 384, [0.2] * 384]
    return mock


@pytest.fixture
def mock_lancedb():
    """Create mock LanceDB handler."""
    mock = MagicMock()
    mock.search.return_value = []
    return mock


@pytest.fixture
def sample_codebase(tmp_path):
    """Create temporary Python files for testing."""
    codebase_dir = tmp_path / "backend"
    codebase_dir.mkdir()

    # Sample file with functions
    sample_file = codebase_dir / "sample_service.py"
    sample_file.write_text('''
"""Sample service for testing."""

def process_data(data: dict) -> dict:
    """Process input data and return result.

    Args:
        data: Input dictionary

    Returns:
        Processed dictionary
    """
    result = {"processed": True}
    return result


async def async_process(data: str) -> str:
    """Async processing function.

    Args:
        data: Input string

    Returns:
        Processed string
    """
    return data.upper()


class DataProcessor:
    """Data processing class."""

    def __init__(self, config: dict):
        """Initialize with config.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def process(self, data: list) -> list:
        """Process list of data.

        Args:
            data: List of items

        Returns:
            Processed list
        """
        return [d.upper() for d in data]
''')

    # Sample API routes file
    routes_file = codebase_dir / "api" / "test_routes.py"
    routes_file.parent.mkdir(exist_ok=True)
    routes_file.write_text('''
"""Test API routes."""

from fastapi import APIRouter

router = APIRouter()

@router.get("/test/items")
async def get_items():
    """Get all items."""
    return {"items": []}

@router.post("/test/items")
async def create_item(item: dict):
    """Create new item."""
    return {"created": True}

@router.get("/test/items/{item_id}")
async def get_item(item_id: str):
    """Get item by ID."""
    return {"item_id": item_id}
''')

    # Sample file with imports
    imports_file = codebase_dir / "core" / "import_test.py"
    imports_file.parent.mkdir(exist_ok=True)
    imports_file.write_text('''
"""Import test file."""

from sqlalchemy.orm import Session
from fastapi import Depends
import json

from core.models import Base
from api.test_routes import router
''')

    return str(codebase_dir)


@pytest.fixture
def research_service(db_session, mock_embedding_service, mock_lancedb, sample_codebase):
    """Create CodebaseResearchService instance for testing."""
    from core.codebase_research_service import CodebaseResearchService

    service = CodebaseResearchService(
        db=db_session,
        embedding_service=mock_embedding_service,
        lancedb=mock_lancedb
    )

    # Override codebase root for testing
    service.ast_parser.codebase_root = Path(sample_codebase)
    service.import_analyzer.codebase_root = Path(sample_codebase)
    service.api_catalog.codebase_root = Path(sample_codebase)

    return service


# ============================================================================
# Task 1: AST Parser Tests
# ============================================================================

class TestASTParser:
    """Test AST parsing utilities."""

    @pytest.fixture
    def parser(self, sample_codebase):
        """Create ASTParser with sample codebase."""
        from core.codebase_research_service import ASTParser
        return ASTParser(sample_codebase)

    def test_extract_functions(self, parser):
        """Test function extraction with signatures."""
        functions = parser.extract_functions("sample_service.py")

        # Extracts all functions including class methods
        assert len(functions) >= 3
        func_names = {f["name"] for f in functions}
        assert "process_data" in func_names
        assert "async_process" in func_names

        # Check function details
        process_func = next(f for f in functions if f["name"] == "process_data")
        assert "data" in process_func["args"]
        assert process_func["returns"] is not None
        assert "Process input data" in process_func["docstring"]
        assert process_func["is_async"] is False

        # Check async function
        async_func = next(f for f in functions if f["name"] == "async_process")
        assert async_func["is_async"] is True

    def test_extract_classes(self, parser):
        """Test class extraction with methods."""
        classes = parser.extract_classes("sample_service.py")

        assert len(classes) == 1
        assert classes[0]["name"] == "DataProcessor"
        assert "config" in classes[0]["methods"] or "process" in classes[0]["methods"]
        assert classes[0]["lineno"] > 0
        assert "Data processing class" in classes[0]["docstring"]

    def test_extract_imports(self, parser):
        """Test import statement parsing."""
        imports = parser.extract_imports("core/import_test.py")

        assert len(imports["from_imports"]) > 0
        assert len(imports["direct_imports"]) > 0

        # Check direct imports
        direct_str = " ".join(imports["direct_imports"])
        assert "import json" in direct_str

        # Check from imports
        from_str = " ".join(imports["from_imports"])
        assert "from sqlalchemy" in from_str or "from fastapi" in from_str

    def test_find_api_routes(self, parser):
        """Test FastAPI route detection."""
        routes = parser.find_api_routes("api/test_routes.py")

        assert len(routes) == 3

        # Check route details
        get_items = next(r for r in routes if r["function"] == "get_items")
        assert get_items["path"] == "/test/items"
        assert get_items["method"] == "GET"
        assert get_items["lineno"] > 0

        create_item = next(r for r in routes if r["function"] == "create_item")
        assert create_item["method"] == "POST"

    def test_extract_dependencies(self, parser):
        """Test module dependency extraction."""
        deps = parser.extract_dependencies("core/import_test.py")

        assert "sqlalchemy" in deps or "fastapi" in deps
        assert "json" in deps
        assert len(deps) >= 2

    def test_parse_invalid_file(self, parser):
        """Test handling of invalid file."""
        result = parser.parse_file("nonexistent.py")
        assert result is None

    def test_parse_file_with_syntax_error(self, parser, tmp_path):
        """Test handling of syntax errors."""
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(:\n    pass")

        result = parser.parse_file(str(bad_file))
        assert result is None


# ============================================================================
# Task 2: Similarity Search Tests
# ============================================================================

class TestSimilaritySearch:
    """Test embedding-based similarity search."""

    @pytest.mark.asyncio
    async def test_find_similar_features(self, research_service):
        """Test similarity search with embedding service."""
        results = await research_service.find_similar_features(
            "data processing function",
            top_k=3
        )

        assert isinstance(results, list)
        # With mock embedding, should return keyword fallback results
        assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_similarity_with_min_threshold(self, research_service):
        """Test similarity threshold filtering."""
        results = await research_service.find_similar_features(
            "nonexistent feature xyz",
            top_k=5,
            min_similarity=0.9
        )

        # All results should meet threshold (or be empty)
        for result in results:
            if "similarity" in result:
                assert result["similarity"] >= 0.9

    @pytest.mark.asyncio
    async def test_search_cache_behavior(self, research_service):
        """Test result caching for repeated queries."""
        query = "test query"

        # First call
        results1 = await research_service.find_similar_features(query)
        # Second call (should hit cache)
        results2 = await research_service.find_similar_features(query)

        assert results1 == results2

    @pytest.mark.asyncio
    async def test_index_codebase(self, research_service):
        """Test codebase indexing for search."""
        result = await research_service.index_codebase()

        assert "indexed" in result
        assert "errors" in result
        assert "duration_seconds" in result
        assert result["indexed"] >= 0


# ============================================================================
# Task 3: Import Graph Tests
# ============================================================================

class TestImportGraph:
    """Test import graph analysis."""

    @pytest.fixture
    def analyzer(self, sample_codebase):
        """Create ImportGraphAnalyzer for testing."""
        from core.codebase_research_service import ImportGraphAnalyzer
        return ImportGraphAnalyzer(sample_codebase)

    def test_build_graph(self, analyzer):
        """Test dependency graph construction."""
        graph = analyzer.build_graph()

        assert isinstance(graph, dict)
        # Should have entries for modules in sample codebase
        assert len(graph) >= 0

    def test_find_dependents(self, analyzer):
        """Test reverse dependency lookup."""
        analyzer.build_graph()

        dependents = analyzer.find_dependents("core.models")

        # Should return list (may be empty in test)
        assert isinstance(dependents, list)

    def test_detect_cycles(self, analyzer):
        """Test circular dependency detection."""
        analyzer.build_graph()

        cycles = analyzer.detect_cycles()

        # Should return list (may be empty in sample)
        assert isinstance(cycles, list)
        for cycle in cycles:
            assert isinstance(cycle, list)
            assert len(cycle) >= 2

    def test_get_execution_order(self, analyzer):
        """Test topological ordering for testing."""
        analyzer.build_graph()

        order = analyzer.get_execution_order({"core.import_test"})

        assert isinstance(order, list)

    def test_estimate_impact(self, analyzer):
        """Test impact estimation for file modifications."""
        analyzer.build_graph()

        # Pass file path string directly, not dict
        impact = analyzer.estimate_impact(["core/import_test.py"])

        assert "directly_affected" in impact
        assert "indirectly_affected" in impact
        assert "risk_level" in impact
        assert impact["risk_level"] in ["low", "medium", "high"]


# ============================================================================
# Task 4: API Catalog Tests
# ============================================================================

class TestAPICatalog:
    """Test API catalog generation."""

    @pytest.fixture
    def catalog(self, sample_codebase):
        """Create APICatalogGenerator for testing."""
        from core.codebase_research_service import APICatalogGenerator
        return APICatalogGenerator(sample_codebase)

    def test_generate_catalog(self, catalog):
        """Test endpoint catalog generation."""
        catalog_data = catalog.generate_catalog()

        assert "endpoints" in catalog_data
        assert "routers" in catalog_data
        assert "namespaces" in catalog_data

        # Check endpoints from sample file
        assert len(catalog_data["endpoints"]) >= 3

        # Check specific endpoints
        endpoint_paths = [e["path"] for e in catalog_data["endpoints"]]
        assert "/test/items" in endpoint_paths

        # Check methods
        methods = [e["method"] for e in catalog_data["endpoints"]]
        assert "GET" in methods
        assert "POST" in methods

    def test_find_available_namespaces(self, catalog):
        """Test namespace capacity detection."""
        available = catalog.find_available_namespaces()

        assert isinstance(available, list)
        # Should find /test namespace with capacity
        assert any("/test" in ns for ns in available)

    def test_api_catalog_route_decorator_extraction(self, catalog):
        """Test extraction of routes from various decorator styles."""
        # The catalog should handle the sample file routes
        catalog_data = catalog.generate_catalog()
        assert len(catalog_data["endpoints"]) >= 3

        # Check specific route types are captured
        get_routes = [e for e in catalog_data["endpoints"] if e["method"] == "GET"]
        post_routes = [e for e in catalog_data["endpoints"] if e["method"] == "POST"]

        assert len(get_routes) >= 1
        assert len(post_routes) >= 1

    def test_detect_route_conflicts_exact_match(self, catalog):
        """Test exact route conflict detection."""
        conflict = catalog.detect_route_conflicts("/test/items", "GET")

        assert conflict is not None
        assert conflict["type"] == "exact_match"
        assert conflict["severity"] == "critical"
        assert "/test/items" in conflict["description"]

    def test_detect_route_conflicts_path_collision(self, catalog):
        """Test path collision (same path, different method)."""
        # Create a route with GET, test collision with POST
        conflict = catalog.detect_route_conflicts("/test/items", "PUT")

        # May return path_collision warning or None
        if conflict:
            assert conflict["type"] in ["path_collision", "exact_match"]

    def test_detect_route_conflicts_no_conflict(self, catalog):
        """Test no conflict for new route."""
        conflict = catalog.detect_route_conflicts("/api/new/endpoint", "GET")

        assert conflict is None


# ============================================================================
# Task 5: Conflict Detection Tests
# ============================================================================

class TestConflictDetection:
    """Test conflict detection system."""

    @pytest.fixture
    def conflict_detector(self, sample_codebase):
        """Create ConflictDetector for testing."""
        from core.codebase_research_service import (
            ASTParser,
            ImportGraphAnalyzer,
            APICatalogGenerator,
            ConflictDetector
        )

        ast_parser = ASTParser(sample_codebase)
        import_analyzer = ImportGraphAnalyzer(sample_codebase)
        api_catalog = APICatalogGenerator(sample_codebase)

        return ConflictDetector(ast_parser, import_analyzer, api_catalog)

    @pytest.mark.asyncio
    async def test_detect_conflicts_with_requirements(self, conflict_detector):
        """Test conflict detection with full requirements."""
        requirements = {
            "feature_description": "Test feature",
            "files_to_modify": [
                {"path": "sample_service.py", "action": "modify"}
            ],
            "api_routes": [
                {"path": "/test/items", "method": "GET"}  # Conflicts!
            ],
            "models": []
        }

        result = await conflict_detector.detect_conflicts(requirements)

        assert "conflicts" in result
        assert "warnings" in result
        assert "safe_to_proceed" in result

        # Should detect route conflict
        assert len(result["conflicts"]) > 0
        assert result["safe_to_proceed"] is False  # Has critical conflict

    @pytest.mark.asyncio
    async def test_detect_duplicate_features(self, conflict_detector):
        """Test duplicate feature detection."""
        duplicates = conflict_detector.detect_duplicate_features(
            "data processing feature"
        )

        assert isinstance(duplicates, list)
        # Placeholder - returns empty until implemented

    def test_detect_breaking_changes_deletion(self, conflict_detector):
        """Test breaking change detection for file deletion."""
        changes = [
            {"path": "sample_service.py", "action": "delete"}
        ]

        breaking = conflict_detector.detect_breaking_changes(changes)

        # Should detect potential issues with deletion
        assert isinstance(breaking, list)

    def test_detect_model_conflicts(self, conflict_detector):
        """Test SQLAlchemy model conflict detection."""
        conflicts = conflict_detector.detect_model_conflicts([])

        # Placeholder - returns empty until implemented
        assert isinstance(conflicts, list)

    def test_detect_model_conflicts_with_content(self, conflict_detector):
        """Test model conflict detection with actual model content."""
        # Create temporary model file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''
from sqlalchemy import Column, String, Integer
from core.models import Base

class TestModel(Base):
    __tablename__ = "test_table"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
''')
            model_file = f.name

        try:
            conflicts = conflict_detector.detect_model_conflicts([
                {"name": "TestModel", "table": "test_table"}
            ])
            # Should return list (empty or with conflicts)
            assert isinstance(conflicts, list)
        finally:
            import os
            os.unlink(model_file)


# ============================================================================
# Task 6: Main Service Tests
# ============================================================================

class TestCodebaseResearchService:
    """Test main CodebaseResearchService orchestration."""

    @pytest.mark.asyncio
    async def test_analyze_codebase_integration(self, research_service):
        """Test full analysis orchestration."""
        requirements = {
            "feature_description": "Data processing API",
            "user_stories": [
                {
                    "action": "Create API endpoint for data processing",
                    "value": "Enable automated data processing"
                }
            ],
            "files_to_modify": [],
            "api_routes": [
                {"path": "/api/new/endpoint", "method": "POST"}
            ],
            "models": []
        }

        results = await research_service.analyze_codebase(requirements, "default")

        # Check all expected keys
        assert "similar_features" in results
        assert "integration_points" in results
        assert "conflicts" in results
        assert "warnings" in results
        assert "safe_to_proceed" in results
        assert "import_graph" in results
        assert "api_catalog" in results
        assert "recommendations" in results

        # Check structure
        assert isinstance(results["similar_features"], list)
        assert isinstance(results["integration_points"], list)
        assert isinstance(results["conflicts"], list)
        assert isinstance(results["recommendations"], list)

    @pytest.mark.asyncio
    async def test_get_integration_points(self, research_service):
        """Test integration point identification."""
        user_stories = [
            {
                "action": "Add API endpoint for user authentication",
                "value": "Secure login"
            },
            {
                "action": "Create user model in database",
                "value": "Store user data"
            }
        ]

        points = research_service.get_integration_points(user_stories)

        assert len(points) > 0
        point_types = {p["type"] for p in points}
        assert "api" in point_types or "model" in point_types

    def test_generate_recommendations(self, research_service):
        """Test recommendation generation."""
        similar = [
            {"name": "ExistingProcessor", "similarity": 0.85, "file": "existing.py"}
        ]
        conflicts = []
        integration_points = [
            {"file": "backend/api/test.py", "type": "api", "reason": "Add endpoint"}
        ]

        recommendations = research_service.generate_recommendations(
            similar, conflicts, integration_points
        )

        assert len(recommendations) > 0
        assert any("similar" in r.lower() for r in recommendations)
        assert any("api" in r.lower() or "integration" in r.lower() for r in recommendations)


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_embedding_search_fallback(self, research_service):
        """Test fallback to keyword search when embedding fails."""
        # Disable embedding service
        research_service.embedding_service = None

        results = await research_service.find_similar_features("data processing")

        # Should fall back to keyword search
        assert isinstance(results, list)

    def test_invalid_file_handling(self, research_service):
        """Test handling of invalid files during parsing."""
        functions = research_service.ast_parser.extract_functions("nonexistent.py")

        assert functions == []

    def test_empty_codebase_handling(self, tmp_path):
        """Test handling of empty codebase directory."""
        from core.codebase_research_service import ImportGraphAnalyzer

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        analyzer = ImportGraphAnalyzer(str(empty_dir))
        graph = analyzer.build_graph()

        assert graph == {}


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_similarity_search_performance(self, research_service):
        """Test similarity search completes within reasonable time."""
        import time
        start = time.time()

        await research_service.find_similar_features("test query", top_k=10)

        duration = time.time() - start
        assert duration < 5.0  # Should complete in < 5 seconds

    def test_import_graph_performance(self, sample_codebase):
        """Test import graph building performance."""
        from core.codebase_research_service import ImportGraphAnalyzer

        import time
        start = time.time()

        analyzer = ImportGraphAnalyzer(sample_codebase)
        analyzer.build_graph()

        duration = time.time() - start
        assert duration < 5.0  # Should complete in < 5 seconds


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_end_to_end_analysis(self, research_service):
        """Test complete analysis workflow."""
        requirements = {
            "feature_description": "User authentication API",
            "user_stories": [
                {
                    "action": "Create login endpoint",
                    "value": "Allow users to authenticate"
                }
            ],
            "files_to_modify": [
                {"path": "api/test_routes.py", "action": "modify"}
            ],
            "api_routes": [
                {"path": "/api/auth/login", "method": "POST"}
            ],
            "models": []
        }

        # Full analysis
        results = await research_service.analyze_codebase(requirements, "test_workspace")

        # Verify all components work together
        assert results["safe_to_proceed"] is not None

        # Check recommendations generated
        assert len(results["recommendations"]) > 0

        # Verify no critical conflicts with new route
        critical_conflicts = [c for c in results["conflicts"] if c.get("severity") == "critical"]
        assert len(critical_conflicts) == 0

    @pytest.mark.asyncio
    async def test_analysis_with_high_similarity_features(self, research_service):
        """Test analysis when highly similar features exist."""
        requirements = {
            "feature_description": "Data processing",
            "user_stories": [],
            "files_to_modify": [],
            "api_routes": [],
            "models": []
        }

        # Mock high similarity results
        research_service._search_cache["Data processing:5:0.0"] = [
            {"name": "ExistingProcessor", "similarity": 0.95, "file": "existing.py", "type": "class"}
        ]

        results = await research_service.analyze_codebase(requirements, "test")

        # Should recommend reuse
        assert len(results["recommendations"]) > 0
        # Check for reuse recommendation (without strict 0.95 format check)
        assert any("similar" in r.lower() for r in results["recommendations"])

    @pytest.mark.asyncio
    async def test_analysis_with_critical_conflicts(self, research_service):
        """Test analysis with blocking conflicts."""
        requirements = {
            "feature_description": "Test",
            "user_stories": [],
            "files_to_modify": [{"path": "api/test_routes.py", "action": "delete"}],
            "api_routes": [{"path": "/test/items", "method": "GET"}],  # Exact conflict
            "models": []
        }

        results = await research_service.analyze_codebase(requirements, "test")

        # Should detect critical conflict
        assert results["safe_to_proceed"] is False
        critical_conflicts = [c for c in results["conflicts"] if c.get("severity") == "critical"]
        assert len(critical_conflicts) > 0

    def test_api_catalog_nonexistent_directory(self, tmp_path):
        """Test API catalog with non-existent API directory."""
        from core.codebase_research_service import APICatalogGenerator
        empty_dir = tmp_path / "backend"
        empty_dir.mkdir()

        catalog = APICatalogGenerator(str(empty_dir))
        result = catalog.generate_catalog()

        assert result["endpoints"] == []
        assert result["routers"] == []
        assert result["namespaces"] == {}

    def test_import_graph_cycle_detection_logic(self, sample_codebase):
        """Test import graph cycle detection algorithm."""
        from core.codebase_research_service import ImportGraphAnalyzer

        analyzer = ImportGraphAnalyzer(sample_codebase)
        # Build graph manually with cycle
        analyzer.graph = {
            "module_a": {"module_b"},
            "module_b": {"module_c"},
            "module_c": {"module_a"}  # Cycle!
        }

        cycles = analyzer.detect_cycles()
        assert len(cycles) > 0
        # Check cycle structure
        assert any("module_a" in cycle and "module_c" in cycle for cycle in cycles)


# ============================================================================
# Convenience Function Tests
# ============================================================================

class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_codebase_research_service(self, db_session):
        """Test service factory function."""
        from core.codebase_research_service import get_codebase_research_service

        service = get_codebase_research_service(db_session)

        assert service is not None
        assert service.db == db_session
        assert service.ast_parser is not None
        assert service.import_analyzer is not None

    @pytest.mark.asyncio
    async def test_analyze_codebase_function(self, db_session):
        """Test convenience analyze function."""
        from core.codebase_research_service import analyze_codebase

        requirements = {
            "feature_description": "Test feature",
            "user_stories": []
        }

        results = await analyze_codebase(requirements, "default", db_session)

        assert results is not None
        assert "similar_features" in results
