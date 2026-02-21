"""
Autonomous Coding CLI Commands

Maintenance commands for autonomous coding agent infrastructure.
Provides codebase indexing, analysis, and debugging utilities.

Usage:
    python -m backend.cli.autonomous_coding_cli index-codebase --force
    python -m backend.cli.autonomous_coding_cli analyze-imports
"""

import asyncio
import click
import logging
import sys
from pathlib import Path
from typing import Optional

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@click.group()
def autonomous():
    """Autonomous coding maintenance commands."""
    pass


@autonomous.command()
@click.option('--force', is_flag=True, help='Force full reindex')
@click.option('--codebase', default='backend', help='Codebase root directory')
def index_codebase(force: bool, codebase: str):
    """
    Index codebase for similarity search.

    Walks all Python files, extracts functions and classes using AST parsing,
    generates embeddings using EmbeddingService, and stores in LanceDB
    for fast similarity search.

    Example:
        python -m backend.cli.autonomous_coding_cli index-codebase --force
    """
    async def _index():
        from core.codebase_research_service import CodebaseResearchService
        from core.database import SessionLocal

        db = SessionLocal()
        try:
            service = CodebaseResearchService(db)
            result = await service.index_codebase(force_refresh=force)

            click.echo(f"✅ Indexed {result['indexed']} files in {result['duration_seconds']:.2f}s")
            if result['errors'] > 0:
                click.echo(f"⚠️  {result['errors']} errors encountered during indexing")

            return 0 if result['errors'] == 0 else 1
        finally:
            db.close()

    return asyncio.run(_index())


@autonomous.command()
@click.option('--codebase', default='backend', help='Codebase root directory')
@click.option('--output', type=click.Path(), help='Output file for graph JSON')
def analyze_imports(codebase: str, output: Optional[str]):
    """
    Analyze import dependencies and detect circular imports.

    Builds dependency graph from Python AST, detects cycles using DFS,
    and reports modules that would be affected by changes.

    Example:
        python -m backend.cli.autonomous_coding_cli analyze-imports --output graph.json
    """
    from core.codebase_research_service import ImportGraphAnalyzer
    import json

    analyzer = ImportGraphAnalyzer(codebase)
    graph = analyzer.build_graph()

    # Detect cycles
    cycles = analyzer.detect_cycles()

    # Report results
    click.echo(f"📊 Import graph built: {len(graph)} modules")
    click.echo(f"🔍 Dependencies analyzed")

    if cycles:
        click.echo(f"⚠️  {len(cycles)} circular dependencies detected:")
        for i, cycle in enumerate(cycles, 1):
            click.echo(f"   {i}. {' → '.join(cycle)}")
    else:
        click.echo("✅ No circular dependencies detected")

    # Export to JSON if requested
    if output:
        with open(output, 'w') as f:
            json.dump({
                "graph": {k: list(v) for k, v in graph.items()},
                "cycles": cycles
            }, f, indent=2)
        click.echo(f"💾 Graph exported to {output}")

    return 1 if cycles else 0


@autonomous.command()
@click.option('--codebase', default='backend', help='Codebase root directory')
def generate_api_catalog(codebase: str):
    """
    Generate catalog of all API endpoints.

    Scans API route files, extracts FastAPI routes with decorators,
    and generates comprehensive catalog with metadata.

    Example:
        python -m backend.cli.autonomous_coding_cli generate-api-catalog
    """
    from core.codebase_research_service import APICatalogGenerator
    import json

    catalog = APICatalogGenerator(codebase)
    result = catalog.generate_catalog()

    click.echo(f"📡 API Catalog generated")
    click.echo(f"   Endpoints: {len(result['endpoints'])}")
    click.echo(f"   Routers: {len(result['routers'])}")
    click.echo(f"   Namespaces: {len(result['namespaces'])}")

    # Show endpoints by namespace
    click.echo("\n📍 Endpoints by namespace:")
    for namespace, count in sorted(result['namespaces'].items()):
        click.echo(f"   {namespace}: {count} routes")

    # Show available namespaces (with capacity)
    available = catalog.find_available_namespaces()
    if available:
        click.echo(f"\n✨ Available namespaces (<10 routes): {len(available)}")
        for ns in available[:5]:
            click.echo(f"   - {ns}")

    return 0


@autonomous.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--codebase', default='backend', help='Codebase root directory')
def parse_ast(file_path: str, codebase: str):
    """
    Parse Python file and extract AST information.

    Shows functions, classes, imports, and API routes found in the file.

    Example:
        python -m backend.cli.autonomous_coding_cli parse-ast backend/api/auth_routes.py
    """
    from core.codebase_research_service import ASTParser

    parser = ASTParser(codebase)

    # Extract all information
    functions = parser.extract_functions(file_path)
    classes = parser.extract_classes(file_path)
    imports = parser.extract_imports(file_path)
    routes = parser.find_api_routes(file_path)
    dependencies = parser.extract_dependencies(file_path)

    click.echo(f"📄 AST Analysis: {file_path}")
    click.echo(f"\n📦 Functions: {len(functions)}")
    for func in functions[:10]:
        async_marker = "async " if func['is_async'] else ""
        click.echo(f"   {async_marker}def {func['name']}({', '.join(func['args'][:3])}{'...' if len(func['args']) > 3 else ''})")

    if len(functions) > 10:
        click.echo(f"   ... and {len(functions) - 10} more")

    click.echo(f"\n🏛️  Classes: {len(classes)}")
    for cls in classes:
        click.echo(f"   class {cls['name']}({', '.join(cls['bases'])})")
        click.echo(f"      Methods: {', '.join(cls['methods'][:5])}{'...' if len(cls['methods']) > 5 else ''}")

    click.echo(f"\n📥 Imports: {len(imports['from_imports']) + len(imports['direct_imports'])}")
    for imp in list(imports['from_imports'])[:5]:
        click.echo(f"   {imp}")
    for imp in list(imports['direct_imports'])[:5]:
        click.echo(f"   {imp}")

    if routes:
        click.echo(f"\n🛣️  API Routes: {len(routes)}")
        for route in routes:
            click.echo(f"   {route['method']} {route['path']} → {route['function']}()")

    click.echo(f"\n🔗 Dependencies: {len(dependencies)}")
    click.echo(f"   {', '.join(sorted(dependencies))}")

    return 0


@autonomous.command()
@click.argument('query')
@click.option('--top-k', default=5, help='Number of results')
@click.option('--codebase', default='backend', help='Codebase root directory')
def search_similar(query: str, top_k: int, codebase: str):
    """
    Find similar code using embedding search.

    Searches for functions and classes similar to the query using
    semantic embeddings. Falls back to keyword matching if embeddings unavailable.

    Example:
        python -m backend.cli.autonomous_coding_cli search-similar "OAuth authentication" --top-k 10
    """
    async def _search():
        from core.codebase_research_service import CodebaseResearchService
        from core.database import SessionLocal

        db = SessionLocal()
        try:
            service = CodebaseResearchService(db)
            results = await service.find_similar_features(query, top_k=top_k)

            if not results:
                click.echo("❌ No similar features found")
                return 1

            click.echo(f"🔍 Found {len(results)} similar features for: {query}")
            for i, result in enumerate(results, 1):
                similarity = result.get('similarity', 0)
                click.echo(f"\n{i}. {result.get('name', 'Unknown')} ({similarity:.1%} match)")
                click.echo(f"   📁 {result.get('file', 'Unknown file')}")
                if result.get('preview'):
                    preview = result['preview'][:100]
                    click.echo(f"   📝 {preview}{'...' if len(result['preview']) > 100 else ''}")

            return 0
        finally:
            db.close()

    return asyncio.run(_search())


@autonomous.command()
def health_check():
    """
    Check autonomous coding infrastructure health.

    Verifies that all required services are available and functioning.

    Example:
        python -m backend.cli.autonomous_coding_cli health-check
    """
    from core.database import SessionLocal
    from core.codebase_research_service import (
        CodebaseResearchService,
        ASTParser,
        ImportGraphAnalyzer,
        APICatalogGenerator
    )

    issues = []

    # Check database
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        click.echo("✅ Database connection OK")
    except Exception as e:
        issues.append(f"Database: {e}")
        click.echo(f"❌ Database connection failed: {e}")

    # Check AST parser
    try:
        parser = ASTParser()
        click.echo("✅ ASTParser initialized")
    except Exception as e:
        issues.append(f"ASTParser: {e}")
        click.echo(f"❌ ASTParser failed: {e}")

    # Check import graph analyzer
    try:
        analyzer = ImportGraphAnalyzer()
        click.echo("✅ ImportGraphAnalyzer initialized")
    except Exception as e:
        issues.append(f"ImportGraphAnalyzer: {e}")
        click.echo(f"❌ ImportGraphAnalyzer failed: {e}")

    # Check API catalog generator
    try:
        catalog = APICatalogGenerator()
        click.echo("✅ APICatalogGenerator initialized")
    except Exception as e:
        issues.append(f"APICatalogGenerator: {e}")
        click.echo(f"❌ APICatalogGenerator failed: {e}")

    # Check embedding service
    try:
        db = SessionLocal()
        service = CodebaseResearchService(db)
        if service.embedding_service:
            click.echo("✅ EmbeddingService available")
        else:
            click.echo("⚠️  EmbeddingService not available (similarity search limited)")
        db.close()
    except Exception as e:
        issues.append(f"CodebaseResearchService: {e}")
        click.echo(f"❌ CodebaseResearchService failed: {e}")

    # Check LanceDB
    try:
        from core.lancedb_handler import get_lancedb_handler
        lancedb = get_lancedb_handler()
        result = lancedb.test_connection()
        if result.get('connected'):
            click.echo("✅ LanceDB connection OK")
        else:
            click.echo(f"⚠️  LanceDB not connected: {result.get('message')}")
    except Exception as e:
        click.echo(f"⚠️  LanceDB unavailable: {e}")

    # Summary
    click.echo(f"\n{'='*60}")
    if not issues:
        click.echo("✅ All systems operational")
        return 0
    else:
        click.echo(f"❌ {len(issues)} issues detected")
        return 1


if __name__ == '__main__':
    autonomous()
