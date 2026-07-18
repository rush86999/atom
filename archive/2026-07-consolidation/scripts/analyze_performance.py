#!/usr/bin/env python3
"""
Performance Analysis Script for Atom Backend

Analyzes the codebase for:
1. N+1 query problems
2. Missing database indexes
3. Caching opportunities
4. Slow endpoints

Usage:
    python scripts/analyze_performance.py
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Set

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Results storage
results = {
    "n_plus_one_issues": [],
    "missing_indexes": [],
    "caching_opportunities": [],
    "slow_endpoints": [],
}


def analyze_n_plus_one_queries():
    """Analyze code for potential N+1 query problems"""
    logger.info("Analyzing for N+1 query patterns...")

    issues_found = 0

    # Check routes for loop queries
    for file in Path("backend/api").glob("*.py"):
        try:
            content = file.read_text()

            # Pattern: loops with db.query inside
            if "for " in content and ".query(" in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if "for " in line and ".query(" in content[i:i+5]:  # Check nearby lines
                        results["n_plus_one_issues"].append({
                            "file": str(file),
                            "line": i + 1,
                            "pattern": "Loop with query",
                            "code": line.strip()
                        })
                        issues_found += 1
        except Exception as e:
            logger.warning(f"Could not analyze {file}: {e}")

    logger.info(f"Found {issues_found} potential N+1 query issues")


def analyze_missing_indexes():
    """Analyze models for missing database indexes"""
    logger.info("Analyzing for missing database indexes...")

    # Read models file
    models_file = Path(__file__).parent.parent / "backend" / "core" / "models.py"
    if not models_file.exists():
        logger.warning(f"models.py not found at {models_file}")
        return

    content = models_file.read_text()
    lines = content.split('\n')

    # Find ForeignKey columns without index=True
    in_model = False
    current_model = None
    current_table = None

    for i, line in enumerate(lines):
        # Check if we're in a class definition
        if line.strip().startswith("class "):
            in_model = True
            parts = line.strip().split()
            if len(parts) >= 2:
                current_model = parts[1].strip("(")

        # Check for __tablename__
        if '__tablename__' in line:
            parts = line.split('=')
            if len(parts) >= 2:
                current_table = parts[1].strip().strip('"')

        # Check for ForeignKey without index
        if 'ForeignKey(' in line and 'index=' not in line:
            # This is a foreign key without an index
            results["missing_indexes"].append({
                "model": current_model,
                "table": current_table,
                "line": i + 1,
                "code": line.strip()
            })

    logger.info(f"Found {len(results['missing_indexes'])} foreign keys without indexes")


def analyze_caching_opportunities():
    """Analyze code for caching opportunities"""
    logger.info("Analyzing for caching opportunities...")

    backend_path = Path(__file__).parent.parent / "backend"

    # Check for patterns
    for file in (backend_path / "core").glob("*.py"):
        try:
            content = file.read_text()

            if "AgentRegistry" in content and ".query(" in content:
                results["caching_opportunities"].append({
                    "type": "agent_registry",
                    "file": str(file.relative_to(Path(__file__).parent.parent)),
                    "recommendation": "Cache AgentRegistry queries by agent_id",
                    "priority": "HIGH"
                })

            if "User" in content and ".query(" in content:
                results["caching_opportunities"].append({
                    "type": "user_queries",
                    "file": str(file.relative_to(Path(__file__).parent.parent)),
                    "recommendation": "Cache User lookups by user_id",
                    "priority": "MEDIUM"
                })
        except Exception as e:
            logger.warning(f"Could not analyze {file}: {e}")

    logger.info(f"Found {len(results['caching_opportunities'])} caching opportunities")


def generate_recommendations():
    """Generate performance improvement recommendations"""
    logger.info("\n" + "="*80)
    logger.info("PERFORMANCE ANALYSIS RESULTS")
    logger.info("="*80 + "\n")

    # N+1 Queries
    logger.info("📊 N+1 QUERY ISSUES")
    if results["n_plus_one_issues"]:
        logger.info(f"Found {len(results['n_plus_one_issues'])} potential issues:")
        for issue in results["n_plus_one_issues"][:5]:  # Show first 5
            logger.info(f"  - {issue['file']}:{issue['line']}: {issue['pattern']}")
        if len(results["n_plus_one_issues"]) > 5:
            logger.info(f"  ... and {len(results['n_plus_one_issues']) - 5} more")
    else:
        logger.info("  No N+1 query issues found")

    # Missing Indexes
    logger.info("\n📊 MISSING DATABASE INDEXES")
    if results["missing_indexes"]:
        logger.info(f"Found {len(results['missing_indexes'])} foreign keys without indexes:")
        for issue in results["missing_indexes"][:5]:
            logger.info(f"  - {issue['model']}: {issue['code']}")
        if len(results["missing_indexes"]) > 5:
            logger.info(f"  ... and {len(results['missing_indexes']) - 5} more")

        logger.info("\n  💡 Recommendation: Add index=True to ForeignKey columns")
        logger.info("     Example: user_id = Column(String(36), ForeignKey(\"users.id\"), index=True)")
    else:
        logger.info("  All foreign keys have indexes")

    # Caching Opportunities
    logger.info("\n📊 CACHING OPPORTUNITIES")
    if results["caching_opportunities"]:
        logger.info(f"Found {len(results['caching_opportunities'])} caching opportunities:")
        for opp in results["caching_opportunities"]:
            logger.info(f"  - [{opp['priority']}] {opp['type']}: {opp['recommendation']}")
            logger.info(f"    File: {opp.get('file', 'N/A')}")

        logger.info("\n  💡 Recommended cache implementations:")
        logger.info("     - Use Redis from core/governance_cache.py for hot data")
        logger.info("     - Cache user sessions, agent registry, configuration")
        logger.info("     - Set appropriate TTL (5-60 minutes for most data)")
    else:
        logger.info("  No obvious caching opportunities found")

    logger.info("\n" + "="*80)
    logger.info("RECOMMENDATIONS")
    logger.info("="*80 + "\n")

    logger.info("1. Add indexes to foreign keys (see detailed list above)")
    logger.info("2. Implement caching for frequently accessed data")
    logger.info("3. Use SQLAlchemy's joinedload() for eager loading relationships")
    logger.info("4. Add pagination to endpoints that return lists")
    logger.info("5. Use selectin/prefetch for optimizing relationship loading")
    logger.info("\nSee docs/DATABASE_MODEL_BEST_PRACTICES.md for implementation patterns")


if __name__ == "__main__":
    try:
        analyze_n_plus_one_queries()
        analyze_missing_indexes()
        analyze_caching_opportunities()
        generate_recommendations()

        # Save results to file
        import json
        with open("scripts/performance_analysis_results.json", "w") as f:
            json.dump(results, f, indent=2)

        logger.info("\n✅ Analysis complete. Results saved to scripts/performance_analysis_results.json")

    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
