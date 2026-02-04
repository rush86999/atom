#!/usr/bin/env python3
"""
Print to Logger Migration Script

Automatically replaces print() statements with logger.info/error/debug calls.

Usage:
    python scripts/migrate_print_to_logging.py [--dry-run] [--file path/to/file.py]

Options:
    --dry-run: Show changes without applying them
    --file: Migrate a single file (default: migrate all non-test files)
"""

import argparse
import ast
import re
from pathlib import Path
from typing import List, Tuple


class PrintToLoggerMigrator:
    """Migrate print() statements to logger calls"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.changes_made = 0

    def migrate_file(self, filepath: str) -> Tuple[bool, List[str]]:
        """Migrate a single Python file"""
        try:
            with open(filepath, 'r') as f:
                content = f.read()

            changes = []
            original_content = content

            # Check if file already has logging
            has_logger = 'logger = logging.getLogger(__name__)' in content

            # Add logger import if not present
            if not has_logger:
                content, import_changes = self._add_logger_import(content)
                changes.extend(import_changes)

            # Replace print() statements
            content, print_changes = self._replace_print_statements(content)
            changes.extend(print_changes)

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

            return False, ["No print() statements found"]

        except Exception as e:
            print(f"Error migrating {filepath}: {e}")
            return False, [f"Error: {e}"]

    def _add_logger_import(self, content: str) -> Tuple[str, List[str]]:
        """Add logging import and logger initialization"""
        changes = []

        # Check if logging is already imported
        if 'import logging' in content:
            # Just add logger initialization after imports
            if 'logger = logging.getLogger(__name__)' not in content:
                # Find the end of imports
                import_end = content.find('\n\n')
                if import_end == -1:
                    import_end = 0

                # Insert logger initialization
                content = content[:import_end] + '\n\nlogger = logging.getLogger(__name__)' + content[import_end:]
                changes.append("Added logger initialization")
        else:
            # Add import logging at the top
            content = 'import logging\n\n' + content

            # Add logger initialization
            if 'logger = logging.getLogger(__name__)' not in content:
                content = 'import logging\n\nlogger = logging.getLogger(__name__)\\n\\n' + content[content.find('\\n')+1:]

            changes.append("Added logging import and logger initialization")

        return content, changes

    def _replace_print_statements(self, content: str) -> Tuple[str, List[str]]:
        """Replace print() statements with logger calls"""
        changes = []

        # Pattern 1: print(string) -> logger.info(string)
        # Pattern 2: print(f"...") -> logger.info(f"...")
        # Pattern 3: print("error:", e) -> logger.error(f"error: {e}")

        # Simple print statements
        patterns = [
            # print("message") -> logger.info("message")
            (r'print\("([^"]+)"\)', r'logger.info("\1")'),

            # print('message') -> logger.info('message')
            (r"print\('([^']+)'\)", r"logger.info('\1')"),

            # print(f"...") -> logger.info(f"...")
            (r'print\(f"([^"]+)"\)', r'logger.info(f"\1")'),
            (r"print\(f'([^']+)'\)", r"logger.info(f'\1')"),

            # print(variable) -> logger.info(str(variable))
            (r'print\((\w+)\)', r'logger.info(str(\1))'),
        ]

        for pattern, replacement in patterns:
            matches = re.findall(pattern, content)
            if matches:
                content = re.sub(pattern, replacement, content)
                changes.append(f"Replaced {len(matches)} print() statement(s)")

        return content, changes


def find_python_files() -> List[str]:
    """Find all Python files (excluding tests)"""
    base_dir = Path(__file__).parent.parent
    python_files = []

    # Find all Python files
    for py_file in base_dir.rglob('*.py'):
        # Exclude test files, __init__.py, and venv
        if (
            not py_file.name.startswith('test_')
            and py_file.name != '__init__.py'
            and 'venv' not in py_file.parts
            and '.venv' not in py_file.parts
            and 'site-packages' not in py_file.parts
        ):
            python_files.append(str(py_file))

    return sorted(python_files)


def main():
    parser = argparse.ArgumentParser(description='Migrate print() to logger')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    parser.add_argument('--file', type=str, help='Migrate a single file')
    args = parser.parse_args()

    migrator = PrintToLoggerMigrator(dry_run=args.dry_run)

    if args.file:
        files = [args.file]
    else:
        files = find_python_files()

    print(f"Found {len(files)} Python files to check\n")

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
        elif 'No print()' in changes[0]:
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
