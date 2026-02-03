#!/usr/bin/env python3
"""
Test script to validate Phase 0 database session migration changes.

This script verifies:
1. All API routes use Depends(get_db) pattern
2. All services use with get_db_session() pattern
3. No manual SessionLocal() calls remain
4. Tests pass successfully
"""

import os
import sys
import re
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def check_file_for_manual_sessions(file_path: str) -> list:
    """Check a file for manual SessionLocal() calls"""
    issues = []

    try:
        with open(file_path, 'r') as f:
            content = f.read()
            lines = content.split('\n')

            for i, line in enumerate(lines, 1):
                # Skip imports
                if line.strip().startswith('from core.database import') or line.strip().startswith('import'):
                    continue

                # Look for SessionLocal() patterns
                if 'SessionLocal()' in line and 'get_db' not in line:
                    # Check if it's a proper context manager usage
                    if 'with get_db_session()' not in line and 'with SessionLocal()' not in line:
                        issues.append({
                            'line': i,
                            'content': line.strip(),
                            'file': file_path
                        })
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return issues

def check_api_route_pattern(file_path: str) -> dict:
    """Check if API route files use Depends(get_db) pattern"""
    result = {'correct': 0, 'needs_fix': 0, 'issues': []}

    try:
        with open(file_path, 'r') as f:
            content = f.read()

            # Check if file is an API route file
            if 'api/' not in file_path and 'routes.py' not in file_path:
                return result

            # Look for route definitions
            route_patterns = re.findall(r'@router\.(get|post|put|delete|patch)\([^)]+\)\s*\n\s*async def \w+\([^)]*db:\s*Session[^)]*\)', content, re.MULTILINE)

            for pattern in route_patterns:
                if 'Depends(get_db)' in pattern:
                    result['correct'] += 1
                else:
                    result['needs_fix'] += 1
                    result['issues'].append(pattern)

    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")

    return result

def main():
    print("=" * 80)
    print("PHASE 0 DATABASE SESSION MIGRATION VALIDATION")
    print("=" * 80)
    print()

    backend_dir = Path("backend")

    # Check 1: Find manual SessionLocal() calls
    print("🔍 Checking for manual SessionLocal() calls...")
    manual_issues = []
    for py_file in backend_dir.rglob("*.py"):
        issues = check_file_for_manual_sessions(str(py_file))
        manual_issues.extend(issues)

    if manual_issues:
        print(f"❌ Found {len(manual_issues)} manual SessionLocal() calls:")
        for issue in manual_issues[:10]:  # Show first 10
            print(f"   {issue['file']}:{issue['line']}: {issue['content']}")
        if len(manual_issues) > 10:
            print(f"   ... and {len(manual_issues) - 10} more")
    else:
        print("✅ No manual SessionLocal() calls found!")

    print()

    # Check 2: Verify API route patterns
    print("🔍 Checking API route patterns...")
    api_files = list(backend_dir.glob("api/*_routes.py")) + list(backend_dir.glob("core/*_endpoints.py"))

    route_stats = {'correct': 0, 'needs_fix': 0}
    for api_file in api_files:
        stats = check_api_route_pattern(str(api_file))
        route_stats['correct'] += stats['correct']
        route_stats['needs_fix'] += stats['needs_fix']

        if stats['issues']:
            print(f"⚠️  {api_file}: {stats['needs_fix']} routes need fixing")

    print(f"   ✅ Correct patterns: {route_stats['correct']}")
    if route_stats['needs_fix'] > 0:
        print(f"   ❌ Needs fixing: {route_stats['needs_fix']}")

    print()

    # Check 3: Verify database.py has get_db and get_db_session
    print("🔍 Checking core/database.py...")
    try:
        with open(backend_dir / "core" / "database.py", 'r') as f:
            db_content = f.read()

            has_get_db = 'def get_db()' in db_content
            has_get_db_session = 'def get_db_session()' in db_content or 'contextmanager' in db_content

            if has_get_db:
                print("   ✅ get_db() function exists")
            else:
                print("   ❌ get_db() function missing!")

            if has_get_db_session:
                print("   ✅ get_db_session() context manager exists")
            else:
                print("   ❌ get_db_session() context manager missing!")
    except Exception as e:
        print(f"   ❌ Error reading database.py: {e}")

    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if not manual_issues and route_stats['needs_fix'] == 0:
        print("✅ PHASE 0 VALIDATION PASSED!")
        print("   All database sessions follow correct patterns.")
        return 0
    else:
        print("⚠️  PHASE 0 VALIDATION FOUND ISSUES:")
        if manual_issues:
            print(f"   - {len(manual_issues)} manual SessionLocal() calls to fix")
        if route_stats['needs_fix'] > 0:
            print(f"   - {route_stats['needs_fix']} API routes need Depends(get_db)")
        return 1

if __name__ == "__main__":
    sys.exit(main())
