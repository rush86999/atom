#!/usr/bin/env python3
"""
Analyze duplicate test files and determine canonical locations.

Canonical Location Rules:
- tests/api/* - API route tests
- tests/core/* - Core service tests
- tests/tools/* - Tool tests
- tests/unit/* - Unit tests (prefer core/api/tools subdirectories)
- tests/integration/* - Integration tests
- tests/test_*.py - Root-level legacy tests (delete if duplicate exists)
"""

import os
import subprocess
from pathlib import Path
from collections import defaultdict

# Priority order for canonical location (highest to lowest)
CANONICAL_PRIORITY = [
    "tests/api/",           # API routes
    "tests/core/",          # Core services
    "tests/tools/",         # Tools
    "tests/integration/",   # Integration tests
    "tests/property_tests/", # Property-based tests
    "tests/unit/",          # Unit tests (last resort)
    "tests/test_",          # Root level (legacy, delete if duplicate exists)
]

def get_file_size(filepath):
    """Get file size in bytes."""
    return os.path.getsize(filepath)

def get_file_modification_time(filepath):
    """Get file modification time."""
    return os.path.getmtime(filepath)

def count_test_functions(filepath):
    """Count test functions in a Python file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            # Count functions starting with 'test_'
            return content.count('def test_')
    except Exception:
        return 0

def analyze_duplicates():
    """Analyze all duplicate test files."""
    # Find all test files
    test_files = []
    for root, dirs, files in os.walk('tests'):
        for file in files:
            if file.startswith('test_') and file.endswith('.py'):
                full_path = os.path.join(root, file)
                test_files.append(full_path)

    # Group by basename
    basenames = defaultdict(list)
    for filepath in test_files:
        basename = os.path.basename(filepath)
        basenames[basename].append(filepath)

    # Filter duplicates (2 or more copies)
    duplicates = {k: v for k, v in basenames.items() if len(v) >= 2}

    files_with_duplicates = sum(1 for files in basenames.values() if len(files) >= 2)
    print(f"Total test files: {len(test_files)}")
    print(f"Files with duplicates: {files_with_duplicates}")
    print(f"Duplicate basenames: {len(duplicates)}")
    print()

    # Analyze each duplicate group
    cleanup_plan = []

    for basename, files in sorted(duplicates.items()):
        print(f"\n{'='*80}")
        print(f"DUPLICATE: {basename}")
        print(f"{'='*80}")

        # Get file stats
        file_stats = []
        for filepath in files:
            stats = {
                'path': filepath,
                'size': get_file_size(filepath),
                'mtime': get_file_modification_time(filepath),
                'test_count': count_test_functions(filepath),
            }
            file_stats.append(stats)

        # Sort by size (largest = most complete)
        file_stats.sort(key=lambda x: x['size'], reverse=True)

        for stat in file_stats:
            print(f"\n  {stat['path']}")
            print(f"    Size: {stat['size']:,} bytes")
            print(f"    Tests: {stat['test_count']} functions")
            print(f"    Modified: {stat['mtime']}")

        # Determine canonical location
        canonical = determine_canonical(file_stats)
        print(f"\n  → CANONICAL: {canonical['path']}")

        # Mark duplicates for deletion
        duplicates_to_delete = [f['path'] for f in file_stats if f['path'] != canonical['path']]
        cleanup_plan.append({
            'basename': basename,
            'canonical': canonical['path'],
            'delete': duplicates_to_delete,
            'reason': canonical['reason']
        })

    return cleanup_plan

def determine_canonical(file_stats):
    """Determine canonical file based on priority and completeness."""
    # Sort by priority
    prioritized = []
    for stat in file_stats:
        priority_score = 0
        for i, prefix in enumerate(CANONICAL_PRIORITY):
            if prefix == "tests/test_":
                # Special case: root level files
                if stat['path'].startswith('tests/test_'):
                    priority_score = i
                    break
            elif stat['path'].startswith(prefix):
                priority_score = i
                break

        prioritized.append({
            **stat,
            'priority_score': priority_score
        })

    # Sort by priority (lower score = higher priority), then by size
    prioritized.sort(key=lambda x: (x['priority_score'], -x['size']))

    canonical = prioritized[0]
    canonical_reason = f"Priority {canonical['priority_score']}, largest file"

    return {
        'path': canonical['path'],
        'reason': canonical_reason
    }

def generate_cleanup_script(cleanup_plan):
    """Generate shell script to delete duplicates."""
    with open('cleanup_duplicates.sh', 'w') as f:
        f.write('#!/bin/bash\n')
        f.write('# Auto-generated cleanup script for duplicate test files\n')
        f.write('# Review before executing!\n\n')
        f.write('set -e\n\n')
        f.write('echo "Cleaning up duplicate test files..."\n')
        f.write('echo "Total files to delete: {}"\n\n'.format(
            sum(len(plan['delete']) for plan in cleanup_plan)
        ))

        for plan in cleanup_plan:
            if plan['delete']:
                f.write(f'\n# {plan["basename"]}\n')
                f.write(f'# Keeping: {plan["canonical"]}\n')
                for filepath in plan['delete']:
                    f.write(f'git rm "{filepath}"\n')

        f.write('\necho "Cleanup complete!"\n')
        f.write('echo "Run: git status to review changes"\n')

    os.chmod('cleanup_duplicates.sh', 0o755)
    print(f"\nGenerated cleanup script: cleanup_duplicates.sh")

def main():
    """Main analysis function."""
    print("="*80)
    print("DUPLICATE TEST FILE ANALYZER")
    print("="*80)
    print()

    cleanup_plan = analyze_duplicates()

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total duplicate groups: {len(cleanup_plan)}")
    total_files_to_delete = sum(len(plan['delete']) for plan in cleanup_plan)
    print(f"Total files to delete: {total_files_to_delete}")

    # Generate cleanup script
    generate_cleanup_script(cleanup_plan)

    print("\nNext steps:")
    print("1. Review the analysis above")
    print("2. Check cleanup_duplicates.sh script")
    print("3. Run: bash cleanup_duplicates.sh")
    print("4. Verify: git status")
    print("5. Commit changes if correct")

if __name__ == '__main__':
    main()
