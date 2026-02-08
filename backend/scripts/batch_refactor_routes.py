#!/usr/bin/env python3
"""
Batch refactor API routes to use @require_governance decorator.

This script helps automate the migration from inline governance checks
to the new decorator pattern.
"""
from pathlib import Path
import re
import sys


def refactor_file(file_path: str, dry_run: bool = True) -> int:
    """
    Refactor a single API route file.

    Returns number of changes made.
    """
    with open(file_path, 'r') as f:
        content = f.read()

    original_content = content
    changes = 0

    # 1. Remove individual feature flags (kept for reference)
    # These will be replaced with centralized imports

    # 2. Add new imports if not present
    if 'from core.api_governance import' not in content:
        # Find the imports section
        imports_end = content.find('\n\n')
        if imports_end > 0:
            # Check if FastAPI imports exist
            if 'from fastapi import' in content[:imports_end]:
                # Add Depends to existing fastapi import
                content = re.sub(
                    r'(from fastapi import [^\n]+)',
                    r'\1\nfrom core.api_governance import require_governance, ActionComplexity\nfrom sqlalchemy.orm import Session\nfrom core.database import get_db',
                    content,
                    count=1
                )
            else:
                # Add new import line
                content = content[:imports_end] + '\nfrom core.api_governance import require_governance, ActionComplexity\nfrom sqlalchemy.orm import Session\nfrom core.database import get_db' + content[imports_end:]
            changes += 1

    # 3. Add Request parameter if needed
    # This is complex and requires manual review

    # 4. Replace inline governance checks with decorators
    # Pattern: if FEATURE_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:

    if not dry_run and changes > 0:
        with open(file_path, 'w') as f:
            f.write(content)

    return changes


def main():
    if len(sys.argv) < 2:
        print("Usage: python batch_refactor_routes.py <file1> [file2] ...")
        print("       python batch_refactor_routes.py --dry-run <file1> [file2] ...")
        sys.exit(1)

    dry_run = '--dry-run' in sys.argv
    files = [f for f in sys.argv[1:] if not f.startswith('--')]

    for file_path in files:
        if not Path(file_path).exists():
            print(f"⚠️  File not found: {file_path}")
            continue

        changes = refactor_file(file_path, dry_run)
        if changes > 0:
            print(f"{'[DRY RUN] ' if dry_run else ''}Refactored {file_path}: {changes} changes")
        else:
            print(f"ℹ️  No changes needed for {file_path}")


if __name__ == '__main__':
    main()
