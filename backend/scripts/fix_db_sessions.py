#!/usr/bin/env python3
"""
Database Session Auto-Fixer

Automatically fixes common database session management patterns.
"""
import os
import re
from typing import List, Tuple


def fix_session_management(content: str) -> Tuple[str, int]:
    """
    Fix database session management patterns in a file.

    Returns (fixed_content, number_of_changes)
    """
    changes = 0
    lines = content.split('\n')
    fixed_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]
        original_line = line

        # Pattern 1: db = SessionLocal() followed by try/finally
        if re.search(r'(\w+)\s*=\s*SessionLocal\(\)', line):
            indent = len(line) - len(line.lstrip())
            var_name = re.search(r'(\w+)\s*=\s*SessionLocal\(\)', line).group(1)

            # Check if next lines have try/finally pattern
            if i + 1 < len(lines) and 'try:' in lines[i + 1]:
                # Skip the db = SessionLocal() line
                i += 1  # Move to try:
                fixed_lines.append(lines[i])  # Keep try:

                # Replace with with get_db_session() pattern
                new_indent = ' ' * indent
                fixed_lines.append(f'{new_indent}from core.database import get_db_session')
                fixed_lines.append(f'{new_indent}')
                fixed_lines.append(f'{new_indent}with get_db_session() as {var_name}:')
                changes += 1

                i += 1
                continue

        # Pattern 2: with SessionLocal() as db:
        if re.search(r'with\s+SessionLocal\(\)\s+as\s+(\w+):', line):
            var_name = re.search(r'with\s+SessionLocal\(\)\s+as\s+(\w+):', line).group(1)
            line = re.sub(r'with\s+SessionLocal\(\)\s+as\s+(\w+):',
                         f'with get_db_session() as {var_name}:', line)
            changes += 1

        # Pattern 3: Remove manual db.close() in with blocks
        if re.search(rf'{var_name}\.close\(\)' if 'var_name' in locals() else r'\w+\.close\(\)', line):
            # Only remove if it's in a finally block
            if 'finally:' in lines[i-1] if i > 0 else False:
                line = '#' + line + '  # Removed: context manager handles cleanup'
                changes += 1

        # Pattern 4: Remove manual db.commit() at end of with block
        # (context manager auto-commits on success)
        # We'll leave this for manual review as it's context-dependent

        fixed_lines.append(line)
        i += 1

    return '\n'.join(fixed_lines), changes


def add_get_db_import(content: str) -> str:
    """Add get_db_session import if not present."""
    if 'from core.database import get_db_session' in content:
        return content

    # Find existing database import
    if 'from core.database import' in content:
        # Add to existing import
        content = re.sub(
            r'from core\.database import ([^\n]+)',
            r'from core.database import \1, get_db_session',
            content
        )
    else:
        # Add new import after imports
        lines = content.split('\n')
        import_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('from ') or line.startswith('import '):
                import_idx = i + 1
            elif import_idx > 0 and not line.startswith('from ') and not line.startswith('import '):
                break

        lines.insert(import_idx, 'from core.database import get_db_session')
        content = '\n'.join(lines)

    return content


def fix_file(file_path: str, dry_run: bool = True) -> Tuple[bool, int]:
    """
    Fix a single file.

    Returns (success, number_of_changes)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        fixed_content, changes = fix_session_management(original_content)

        if changes > 0:
            # Add import if needed
            if 'get_db_session' in fixed_content:
                fixed_content = add_get_db_import(fixed_content)

            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)

            return True, changes

        return False, 0

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False, 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Auto-fix database session management')
    parser.add_argument('--file', help='File to fix')
    parser.add_argument('--list', help='File with list of files to fix')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Show changes without applying (default: True)')
    parser.add_argument('--apply', action='store_true',
                       help='Actually apply changes (disables dry-run)')

    args = parser.parse_args()

    if args.apply:
        args.dry_run = False

    files_to_fix = []

    if args.file:
        files_to_fix.append(args.file)
    elif args.list:
        with open(args.list, 'r') as f:
            files_to_fix = [line.strip() for line in f if line.strip()]
    else:
        print("Usage: python fix_db_sessions.py --file <file> or --list <file>")
        return

    mode = "DRY RUN" if args.dry_run else "APPLY"
    print(f"Mode: {mode}")
    print(f"Files to fix: {len(files_to_fix)}")
    print()

    total_changes = 0
    success_count = 0

    for file_path in files_to_fix:
        if not os.path.exists(file_path):
            print(f"⚠️  File not found: {file_path}")
            continue

        print(f"Processing: {file_path}")
        success, changes = fix_file(file_path, args.dry_run)

        if success:
            print(f"  ✅ {changes} changes")
            total_changes += changes
            success_count += 1
        else:
            print(f"  ℹ️  No changes needed")

    print()
    print(f"Summary: {success_count} files, {total_changes} changes")
    if args.dry_run:
        print("⚠️  DRY RUN MODE - No files were modified")
        print("Use --apply to actually apply changes")


if __name__ == '__main__':
    main()
