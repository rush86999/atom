#!/usr/bin/env python3
"""
Database Session Migration Script

Identifies and helps migrate manual database session management to the
context manager pattern.

Usage:
    python scripts/migrate_db_sessions.py          # Identify files to migrate
    python scripts/migrate_db_sessions.py --fix    # Auto-fix simple cases
"""
import ast
import os
import re
from pathlib import Path
from typing import List, Tuple


def find_manual_session_patterns(file_path: str) -> List[Tuple[int, str, str]]:
    """
    Find manual session management patterns in a Python file.

    Returns list of (line_number, pattern_type, matched_line)
    """
    patterns = [
        (r'SessionLocal\(\)', 'Direct SessionLocal() call'),
        (r'with\s+SessionLocal\(\)', 'Manual with SessionLocal()'),
        (r'db\s*=\s*SessionLocal\(\)', 'Variable assignment'),
        (r'\.close\(\)', 'Manual close() call'),
        (r'\.commit\(\)', 'Manual commit() call'),
    ]

    findings = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            for pattern, description in patterns:
                if re.search(pattern, line):
                    findings.append((line_num, description, line.strip()))
                    break  # Only report first match per line

    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return findings


def scan_directory(directory: str, exclude_dirs: List[str] = None) -> dict:
    """
    Scan directory for Python files with manual session management.
    """
    if exclude_dirs is None:
        exclude_dirs = ['venv', '__pycache__', '.pytest_cache',
                       'node_modules', '.git', 'migrations', 'alembic']

    results = {
        'files_with_manual_sessions': [],
        'total_files_scanned': 0,
        'files_with_issues': {}
    }

    for root, dirs, files in os.walk(directory):
        # Remove excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                results['total_files_scanned'] += 1

                findings = find_manual_session_patterns(file_path)
                if findings:
                    results['files_with_manual_sessions'].append(file_path)
                    results['files_with_issues'][file_path] = findings

    return results


def categorize_by_priority(results: dict) -> dict:
    """
    Categorize files by migration priority.
    """
    high_priority = []
    medium_priority = []
    low_priority = []

    for file_path, issues in results['files_with_issues'].items():
        line_count = len(issues)

        # High priority: Service layer files with multiple issues
        if any(path in file_path for path in ['service', 'services', 'core']):
            if line_count >= 3:
                high_priority.append((file_path, line_count))
            else:
                medium_priority.append((file_path, line_count))

        # Medium priority: API routes, integrations
        elif any(path in file_path for path in ['api', 'integrations']):
            if line_count >= 3:
                medium_priority.append((file_path, line_count))
            else:
                low_priority.append((file_path, line_count))

        # Low priority: Scripts, tests, tools
        else:
            low_priority.append((file_path, line_count))

    # Sort by issue count (descending)
    high_priority.sort(key=lambda x: x[1], reverse=True)
    medium_priority.sort(key=lambda x: x[1], reverse=True)
    low_priority.sort(key=lambda x: x[1], reverse=True)

    return {
        'high': high_priority,
        'medium': medium_priority,
        'low': low_priority
    }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Migrate database session management')
    parser.add_argument('--directory', default='.', help='Directory to scan')
    parser.add_argument('--fix', action='store_true', help='Auto-fix simple cases')
    parser.add_argument('--output', help='Output file for results')
    args = parser.parse_args()

    print("=" * 80)
    print("Database Session Migration Scanner")
    print("=" * 80)
    print()

    print(f"Scanning directory: {args.directory}")
    print()

    results = scan_directory(args.directory)

    print(f"Files scanned: {results['total_files_scanned']}")
    print(f"Files with manual sessions: {len(results['files_with_manual_sessions'])}")
    print()

    if not results['files_with_manual_sessions']:
        print("✅ No files with manual session management found!")
        return

    # Categorize by priority
    categorized = categorize_by_priority(results)

    # Print results
    print("Priority Classification:")
    print("-" * 80)

    if categorized['high']:
        print(f"\n🔴 HIGH PRIORITY ({len(categorized['high'])} files):")
        print("   Service layer files with multiple manual session patterns")
        for file_path, count in categorized['high'][:10]:
            rel_path = os.path.relpath(file_path, args.directory)
            print(f"   - {rel_path} ({count} issues)")

    if categorized['medium']:
        print(f"\n🟡 MEDIUM PRIORITY ({len(categorized['medium'])} files):")
        print("   API routes and integrations")
        for file_path, count in categorized['medium'][:10]:
            rel_path = os.path.relpath(file_path, args.directory)
            print(f"   - {rel_path} ({count} issues)")

    if categorized['low']:
        print(f"\n🟢 LOW PRIORITY ({len(categorized['low'])} files):")
        print("   Scripts, tests, and tools")
        for file_path, count in categorized['low'][:10]:
            rel_path = os.path.relpath(file_path, args.directory)
            print(f"   - {rel_path} ({count} issues)")

    print()
    print("=" * 80)
    print(f"Total: {len(results['files_with_manual_sessions'])} files need migration")
    print("=" * 80)

    # Write output file if requested
    if args.output:
        with open(args.output, 'w') as f:
            f.write("# Database Session Migration Report\n\n")
            f.write(f"Total files: {len(results['files_with_manual_sessions'])}\n\n")

            f.write("## High Priority\n\n")
            for file_path, count in categorized['high']:
                rel_path = os.path.relpath(file_path, args.directory)
                f.write(f"- {rel_path} ({count} issues)\n")

            f.write("\n## Medium Priority\n\n")
            for file_path, count in categorized['medium']:
                rel_path = os.path.relpath(file_path, args.directory)
                f.write(f"- {rel_path} ({count} issues)\n")

            f.write("\n## Low Priority\n\n")
            for file_path, count in categorized['low']:
                rel_path = os.path.relpath(file_path, args.directory)
                f.write(f"- {rel_path} ({count} issues)\n")

        print(f"\nReport written to: {args.output}")


if __name__ == '__main__':
    main()
