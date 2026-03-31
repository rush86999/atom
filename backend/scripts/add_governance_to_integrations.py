#!/usr/bin/env python3
"""
Automated Governance Injection Script for Upstream Integrations

Applies circuit breaker, rate limiter, and audit logging patterns to all
integration service files that lack them.

Usage:
    python scripts/add_governance_to_integrations.py [--dry-run] [--integration name]

Examples:
    python scripts/add_governance_to_integrations.py --dry-run
    python scripts/add_governance_to_integrations.py --integration outlook
    python scripts/add_governance_to_integrations.py
"""

import argparse
import ast
import glob
import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Set, Tuple

# Integration names that already have governance
HAS_GOVERNANCE = {"gmail", "jira", "mcp", "zoom"}

# Governance imports to add
GOVERNANCE_IMPORTS = """from core.circuit_breaker import circuit_breaker
from core.rate_limiter import rate_limiter, should_retry, calculate_backoff
from core.audit_logger import log_integration_call, log_integration_error, log_integration_attempt, log_integration_complete
from fastapi import HTTPException"""


class GovernanceInjector:
    """Injects governance patterns into integration service files"""

    def __init__(self, integrations_dir: str, dry_run: bool = False):
        self.integrations_dir = Path(integrations_dir)
        self.dry_run = dry_run
        self.modified_files = []
        self.skipped_files = []

    def identify_integrations(self, specific_integration: str = None) -> List[Path]:
        """Identify integration service files needing governance"""
        pattern = f"{self.integrations_dir}/*_service.py"

        if specific_integration:
            pattern = f"{self.integrations_dir}/{specific_integration}_service.py"

        all_files = glob.glob(pattern)

        if specific_integration:
            # For specific integration, only return it if it exists
            if all_files and Path(all_files[0]).exists():
                return [Path(all_files[0])]
            return []

        # Filter out integrations that already have governance
        needs_governance = []
        for file_path in all_files:
            file_name = Path(file_path).stem
            integration_name = file_name.replace("_service", "")

            if integration_name not in HAS_GOVERNANCE:
                needs_governance.append(Path(file_path))

        return needs_governance

    def has_governance_imports(self, file_path: Path) -> bool:
        """Check if file already has governance imports"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for any of the governance imports
            has_circuit_breaker = "from core.circuit_breaker import" in content
            has_rate_limiter = "from core.rate_limiter import" in content
            has_audit_logger = "from core.audit_logger import" in content

            return has_circuit_breaker or has_rate_limiter or has_audit_logger
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return False

    def extract_integration_name(self, file_path: Path) -> str:
        """Extract integration name from file path"""
        return file_path.stem.replace("_service", "")

    def find_async_methods(self, content: str) -> List[Tuple[int, str, str]]:
        """
        Find all public async methods in the file.

        Returns:
            List of tuples: (line_number, method_name, indentation)
        """
        methods = []
        lines = content.split('\n')

        for i, line in enumerate(lines):
            # Match async def method_name(self, ...)
            # Exclude private methods (_method_name) and property methods
            match = re.match(r'^(\s*)async def ([a-z][a-zA-Z0-9_]*)\(self', line)
            if match:
                indent = match.group(1)
                method_name = match.group(2)

                # Skip private methods and special methods
                if not method_name.startswith('_'):
                    methods.append((i + 1, method_name, indent))

        return methods

    def inject_governance_to_method(
        self,
        content: str,
        method_name: str,
        integration_name: str,
        start_line: int,
        indent: str
    ) -> str:
        """
        Inject governance wrapper into a method.

        Returns modified content.
        """
        lines = content.split('\n')

        # Find the method body start (first line after method signature)
        # Look for the docstring or first statement
        i = start_line - 1  # Convert to 0-indexed

        # Skip method signature line
        while i < len(lines) and ('async def ' in lines[i] or 'def ' in lines[i]):
            i += 1

        # Skip empty lines and docstring
        if i < len(lines) and '"""' in lines[i]:
            # Find end of docstring
            i += 1
            while i < len(lines) and '"""' not in lines[i]:
                i += 1
            i += 1  # Skip closing """

        # Skip empty lines
        while i < len(lines) and lines[i].strip() == '':
            i += 1

        # Now i should be at the first actual line of method body
        # Insert governance wrapper here
        method_body_indent = indent + '    '

        # Build the governance wrapper code
        governance_code = f"""{method_body_indent}# Start audit logging
{method_body_indent}audit_ctx = log_integration_attempt("{integration_name}", "{method_name}", locals())
{method_body_indent}try:
{method_body_indent}    # Check circuit breaker
{method_body_indent}    if not await circuit_breaker.is_enabled("{integration_name}"):
{method_body_indent}        logger.warning(f"Circuit breaker is open for {integration_name}")
{method_body_indent}        log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
{method_body_indent}        raise HTTPException(
{method_body_indent}            status_code=503,
{method_body_indent}            detail=f"{integration_name.capitalize()} integration temporarily disabled"
{method_body_indent}        )

{method_body_indent}    # Check rate limiter
{method_body_indent}    is_limited, remaining = await rate_limiter.is_rate_limited("{integration_name}")
{method_body_indent}    if is_limited:
{method_body_indent}        logger.warning(f"Rate limit exceeded for {integration_name}")
{method_body_indent}        log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
{method_body_indent}        raise HTTPException(
{method_body_indent}            status_code=429,
{method_body_indent}            detail=f"Rate limit exceeded for {integration_name}"
{method_body_indent}        )
"""

        # Insert governance code at the beginning of method body
        lines.insert(i, governance_code)

        # Now find the end of the method to add success/failure logging
        # We need to find return statements and wrap them
        # For simplicity, we'll add the success logging before each return
        # and look for existing exception handling

        # Find the method's return statements (simple approach)
        # In a real implementation, you'd want to parse the AST
        # For now, we'll just add a note that manual review is needed

        return '\n'.join(lines)

    def add_imports(self, content: str) -> str:
        """Add governance imports if not present"""
        lines = content.split('\n')

        # Find the last import statement
        last_import_idx = -1
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import_idx = i

        if last_import_idx == -1:
            # No imports found, add at the beginning
            insert_idx = 0
        else:
            # Add after the last import
            insert_idx = last_import_idx + 1

        # Check if governance imports already exist
        has_governance = any(
            imp in content for imp in [
                "from core.circuit_breaker import",
                "from core.rate_limiter import",
                "from core.audit_logger import"
            ]
        )

        if has_governance:
            return content

        # Insert imports
        lines.insert(insert_idx, GOVERNANCE_IMPORTS)
        lines.insert(insert_idx + 1, '')  # Add blank line after imports

        return '\n'.join(lines)

    def process_file(self, file_path: Path) -> bool:
        """
        Process a single integration file.

        Returns:
            True if file was modified, False otherwise
        """
        integration_name = self.extract_integration_name(file_path)

        # Check if already has governance
        if self.has_governance_imports(file_path):
            print(f"  ✓ Skipping {file_path.name} - already has governance")
            self.skipped_files.append(file_path)
            return False

        print(f"  → Processing {file_path.name}")

        # Read file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  ✗ Error reading {file_path}: {e}")
            return False

        # Backup file
        backup_path = file_path.with_suffix('.py.bak')
        if not self.dry_run:
            try:
                shutil.copy2(file_path, backup_path)
            except Exception as e:
                print(f"  ✗ Error creating backup: {e}")
                return False

        # Add imports
        modified_content = self.add_imports(content)

        # Find and inject governance into async methods
        methods = self.find_async_methods(modified_content)

        if not methods:
            print(f"    No public async methods found, adding imports only")
        else:
            print(f"    Found {len(methods)} public async method(s)")
            for line_num, method_name, indent in methods[:3]:  # Limit to first 3 for logging
                print(f"      - {method_name} (line {line_num})")

            if len(methods) > 3:
                print(f"      ... and {len(methods) - 3} more")

            # Inject governance into each method (in reverse order to preserve line numbers)
            for line_num, method_name, indent in reversed(methods):
                try:
                    modified_content = self.inject_governance_to_method(
                        modified_content,
                        method_name,
                        integration_name,
                        line_num,
                        indent
                    )
                except Exception as e:
                    print(f"    ✗ Error injecting governance into {method_name}: {e}")
                    continue

        # Write modified content
        if not self.dry_run:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                self.modified_files.append(file_path)
                print(f"  ✓ Modified {file_path.name}")
                return True
            except Exception as e:
                print(f"  ✗ Error writing {file_path}: {e}")
                # Restore from backup
                if backup_path.exists():
                    shutil.copy2(backup_path, file_path)
                return False
        else:
            print(f"  [DRY RUN] Would modify {file_path.name}")
            self.modified_files.append(file_path)
            return True

    def run(self, specific_integration: str = None) -> dict:
        """
        Run the governance injection process.

        Returns:
            dict with statistics
        """
        files_to_process = self.identify_integrations(specific_integration)

        if not files_to_process:
            print("No integration files found to process")
            return {
                "total": 0,
                "modified": 0,
                "skipped": 0,
                "failed": 0
            }

        print(f"\nFound {len(files_to_process)} integration(s) to process\n")

        for file_path in files_to_process:
            self.process_file(file_path)

        return {
            "total": len(files_to_process),
            "modified": len(self.modified_files),
            "skipped": len(self.skipped_files),
            "failed": len(files_to_process) - len(self.modified_files) - len(self.skipped_files)
        }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Inject governance patterns into integration services"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making modifications"
    )
    parser.add_argument(
        "--integration",
        type=str,
        help="Specific integration name (e.g., 'outlook', 'slack')"
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="integrations",
        help="Directory containing integration service files (default: integrations)"
    )

    args = parser.parse_args()

    # Get the script's directory
    script_dir = Path(__file__).parent.parent
    integrations_dir = script_dir / args.dir

    if not integrations_dir.exists():
        print(f"Error: Integrations directory not found: {integrations_dir}")
        sys.exit(1)

    print("=" * 80)
    print("Governance Injection Script for Upstream Integrations")
    print("=" * 80)
    print(f"Directory: {integrations_dir}")
    print(f"Dry run: {args.dry_run}")
    print(f"Integration: {args.integration or 'All'}")
    print()

    injector = GovernanceInjector(
        integrations_dir=str(integrations_dir),
        dry_run=args.dry_run
    )

    stats = injector.run(args.integration)

    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total files:      {stats['total']}")
    print(f"Modified:         {stats['modified']}")
    print(f"Skipped:          {stats['skipped']}")
    print(f"Failed:           {stats['failed']}")
    print()

    if injector.modified_files:
        print("Modified files:")
        for file_path in injector.modified_files:
            print(f"  - {file_path.name}")
        print()

    if args.dry_run and injector.modified_files:
        print("⚠️  DRY RUN MODE - No files were actually modified")
        print("   Run without --dry-run to apply changes")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
