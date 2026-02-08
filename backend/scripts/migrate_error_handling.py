#!/usr/bin/env python3
"""
Error Handling Migration Script

Automatically migrates service layer files to use standardized error handling.

Usage:
    python scripts/migrate_error_handling.py [--dry-run] [--file path/to/file.py]

Options:
    --dry-run: Show changes without applying them
    --file: Migrate a single file (default: migrate all service files)
"""

import argparse
import ast
import os
from pathlib import Path
import re
from typing import List, Tuple


class ErrorHandlingMigrator:
    """Migrate Python files to standardized error handling"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.changes_made = 0

    def migrate_file(self, filepath: str) -> Tuple[bool, List[str]]:
        """
        Migrate a single Python file.

        Returns:
            Tuple of (success, list of changes made)
        """
        try:
            with open(filepath, 'r') as f:
                content = f.read()

            changes = []
            original_content = content

            # Check if file already has standardized error handling
            if '"success": True' in content or '"success": False' in content:
                return True, ["Already using standardized error handling"]

            # Pattern 1: Replace `raise HTTPException` in service layer
            if self._is_service_file(filepath):
                content, pattern1_changes = self._replace_http_exception(content)
                changes.extend(pattern1_changes)

            # Pattern 2: Replace `return []` on error
            content, pattern2_changes = self._replace_empty_list_return(content)
            changes.extend(pattern2_changes)

            # Pattern 3: Replace APIRouter with BaseAPIRouter (for API files)
            if self._is_api_file(filepath):
                content, pattern3_changes = self._replace_api_router(content)
                changes.extend(pattern3_changes)

            # Write changes
            if content != original_content and changes:
                if self.dry_run:
                    print(f"\n{'='*60}")
                    print(f"File: {filepath}")
                    print(f"{'='*60}")
                    for change in changes:
                        print(f"  - {change}")
                else:
                    with open(filepath, 'w') as f:
                        f.write(content)
                    self.changes_made += 1

                return True, changes

            return False, ["No changes needed"]

        except Exception as e:
            print(f"Error migrating {filepath}: {e}")
            return False, [f"Error: {e}"]

    def _is_service_file(self, filepath: str) -> bool:
        """Check if file is a service layer file"""
        path_parts = Path(filepath).parts
        return 'integrations' in path_parts or 'accounting' in path_parts

    def _is_api_file(self, filepath: str) -> bool:
        """Check if file is an API route file"""
        path_parts = Path(filepath).parts
        return 'api' in path_parts

    def _replace_http_exception(self, content: str) -> Tuple[str, List[str]]:
        """Replace raise HTTPException with structured error returns"""
        changes = []

        # Pattern: raise HTTPException(status_code=404, detail="...")
        pattern = r'raise HTTPException\(status_code=(\d+),\s*detail="([^"]+)"'

        def replace_func(match):
            status_code = match.group(1)
            detail_message = match.group(2)

            # Map status codes to error codes
            error_code_map = {
                '400': 'VALIDATION_ERROR',
                '404': 'NOT_FOUND',
                '409': 'CONFLICT',
                '500': 'INTERNAL_ERROR'
            }
            error_code = error_code_map.get(status_code, 'UNKNOWN_ERROR')

            replacement = f'''return {{
                "success": False,
                "error": {{
                    "code": "{error_code}",
                    "message": "{detail_message}"
                }}
            }}'''

            changes.append(f"Replaced HTTPException {status_code} with structured error")
            return replacement

        content = re.sub(pattern, replace_func, content)
        return content, changes

    def _replace_empty_list_return(self, content: str) -> Tuple[str, List[str]]:
        """Replace `return []` in error cases with structured error"""
        changes = []

        # Pattern: except ...:\n        return []
        pattern = r'except ([^:]+):\s+return \[\]'

        def replace_func(match):
            exception_type = match.group(1)

            replacement = f'''except {exception_type}:
            logger.error(f"Error in {{func_name}}: {{{exception_type}}}")
            return {{
                "success": False,
                "error": {{
                    "code": "INTERNAL_ERROR",
                    "message": "An error occurred"
                }}
            }}'''

            changes.append("Replaced `return []` with structured error")
            return replacement

        content = re.sub(pattern, replace_func, content)
        return content, changes

    def _replace_api_router(self, content: str) -> Tuple[str, List[str]]:
        """Replace APIRouter with BaseAPIRouter"""
        changes = []

        # Pattern: from fastapi import APIRouter
        if 'from fastapi import APIRouter' in content:
            content = content.replace(
                'from fastapi import APIRouter',
                'from core.base_routes import BaseAPIRouter'
            )
            changes.append("Replaced fastapi.APIRouter with BaseAPIRouter")

        # Pattern: router = APIRouter(...)
        pattern = r'router = APIRouter\('
        if re.search(pattern, content):
            content = re.sub(pattern, 'router = BaseAPIRouter(', content)
            changes.append("Updated router initialization to BaseAPIRouter")

        return content, changes


def find_service_files() -> List[str]:
    """Find all service layer files"""
    base_dir = Path(__file__).parent.parent
    service_files = []

    # Find integration files
    integrations_dir = base_dir / 'integrations'
    if integrations_dir.exists():
        service_files.extend(integrations_dir.glob('**/*.py'))

    # Find accounting files
    accounting_dir = base_dir / 'accounting'
    if accounting_dir.exists():
        service_files.extend(accounting_dir.glob('**/*.py'))

    # Find API files
    api_dir = base_dir / 'api'
    if api_dir.exists():
        service_files.extend(api_dir.glob('**/*.py'))

    # Filter out test files and __init__.py
    service_files = [
        str(f) for f in service_files
        if not f.name.startswith('__') and 'test_' not in f.name
    ]

    return sorted(service_files)


def main():
    parser = argparse.ArgumentParser(description='Migrate error handling patterns')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    parser.add_argument('--file', type=str, help='Migrate a single file')
    args = parser.parse_args()

    migrator = ErrorHandlingMigrator(dry_run=args.dry_run)

    if args.file:
        files = [args.file]
    else:
        files = find_service_files()

    print(f"Found {len(files)} files to check\n")

    results = {
        'success': 0,
        'no_changes': 0,
        'errors': 0
    }

    for filepath in files:
        success, changes = migrator.migrate_file(filepath)

        if success:
            results['success'] += 1
            if not args.dry_run:
                print(f"✓ {filepath}")
                for change in changes:
                    print(f"  - {change}")
        elif 'No changes needed' in changes[0] or 'Already using' in changes[0]:
            results['no_changes'] += 1
        else:
            results['errors'] += 1
            print(f"✗ {filepath}: {changes[0]}")

    print(f"\n{'='*60}")
    print("Migration Summary:")
    print(f"  Files migrated: {results['success']}")
    print(f"  Files unchanged: {results['no_changes']}")
    print(f"  Files with errors: {results['errors']}")
    print(f"{'='*60}")

    if args.dry_run:
        print("\nDRY RUN MODE - No changes were applied")
        print("Run without --dry-run to apply changes")


if __name__ == '__main__':
    main()
