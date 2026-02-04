#!/usr/bin/env python3
"""
AST-based auto-fix script for indentation errors in Atom backend.

This script uses the tokenize module to precisely fix indentation issues
where `with get_db_session() as db:` is followed by an incorrectly indented `try:` block.
"""

import os
import sys
import tokenize
from pathlib import Path
from typing import List, Tuple
import io

# Backend directory
BACKEND_DIR = Path("/Users/rushiparikh/projects/atom/backend")


def fix_file_tokens(filepath: Path) -> Tuple[bool, str]:
    """
    Fix indentation issues using token-level processing.
    Returns (success, message)
    """
    try:
        with open(filepath, 'rb') as f:
            tokens = list(tokenize.tokenize(f.readline))

        # Convert tokens back to source with fixes
        result_tokens = []
        i = 0

        while i < len(tokens):
            token = tokens[i]

            # Look for pattern: WITH_KEYWORD ('with') followed by NAME ('get_db_session')
            # then incorrectly indented try block
            if token.type == tokenize.NAME and token.string == 'with':
                # Check if this is our pattern
                j = i
                found_get_db_session = False
                found_try_at_wrong_indent = False

                # Look ahead for get_db_session
                while j < len(tokens) and tokens[j].type != tokenize.NEWLINE:
                    if tokens[j].type == tokenize.NAME and tokens[j].string == 'get_db_session':
                        found_get_db_session = True
                    j += 1

                if found_get_db_session:
                    # Now look for the try statement
                    # Skip to next line
                    while j < len(tokens) and tokens[j].type in (tokenize.NEWLINE, tokenize.NL, tokenize.COMMENT):
                        j += 1

                    # Check if next line is 'try' with insufficient indentation
                    if j < len(tokens) and tokens[j].type == tokenize.NAME and tokens[j].string == 'try':
                        # Check indentation - should be more than 'with' statement
                        with_indent = tokens[i].start[1]
                        try_indent = tokens[j].start[1]

                        if try_indent <= with_indent + 1:
                            # Found the issue! We need to increase try indentation
                            # Create a new token with proper indentation
                            new_start = (tokens[j].start[0], with_indent + 4)
                            if tokens[j].end[1] == tokens[j].start[1]:  # Single token
                                new_end = (tokens[j].end[0], with_indent + 4 + len(tokens[j].string))
                            else:
                                new_end = tokens[j].end
                                new_end = (new_end[0], new_end[1] + (with_indent + 4 - try_indent))

                            fixed_token = tokenize.TokenInfo(
                                type=tokens[j].type,
                                string=tokens[j].string,
                                start=new_start,
                                end=new_end,
                                line=tokens[j].line
                            )
                            result_tokens.append(fixed_token)
                            i = j + 1
                            continue

            result_tokens.append(token)
            i += 1

        # Reconstruct source from tokens
        source_lines = []
        current_line = 1
        current_col = 0

        for token in result_tokens:
            if token.type == tokenize.ENCODING:
                continue

            # Handle line breaks
            while current_line < token.start[0]:
                source_lines.append('\n')
                current_line += 1
                current_col = 0

            # Handle column spacing
            while current_col < token.start[1]:
                source_lines.append(' ')
                current_col += 1

            # Add the token string
            if token.type != tokenize.NEWLINE and token.type != tokenize.NL:
                source_lines.append(token.string)
                current_col += len(token.string)
            else:
                source_lines.append('\n')
                current_line += 1
                current_col = 0

        # Join and write back
        fixed_content = ''.join(source_lines)

        with open(filepath, 'w') as f:
            f.write(fixed_content)

        return True, "Fixed indentation"

    except Exception as e:
        return False, f"Error: {str(e)}"


def fix_simple_pattern(filepath: Path) -> bool:
    """
    Simple line-based fix for the specific pattern.
    """
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()

        new_lines = []
        i = 0
        fixes = 0

        while i < len(lines):
            line = lines[i]

            # Check for pattern: "with get_db_session() as db:"
            if 'with get_db_session() as db:' in line:
                # Get indentation
                indent = len(line) - len(line.lstrip())
                new_lines.append(line)
                i += 1

                # Check next line for "try:" at wrong indentation
                if i < len(lines):
                    next_line = lines[i]
                    next_indent = len(next_line) - len(next_line.lstrip())

                    # If "try:" is at same or less indentation than "with"
                    if 'try:' in next_line and next_indent <= indent + 1:
                        # Fix indentation
                        fixed_try = ' ' * (indent + 4) + 'try:' + '\n'
                        new_lines.append(fixed_try)
                        fixes += 1
                        i += 1

                        # Continue with remaining lines
                        while i < len(lines):
                            new_lines.append(lines[i])
                            i += 1
                        break

            new_lines.append(line)
            i += 1

        if fixes > 0:
            with open(filepath, 'w') as f:
                f.writelines(new_lines)
            return True

        return False

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def scan_and_fix():
    """Scan all Python files and fix indentation errors."""
    print("=" * 70)
    print("Auto-fixing indentation errors in Atom backend")
    print("=" * 70)
    print()

    # List of known problematic files
    problematic_files = [
        "core/business_agents.py",
        "core/chat_session_manager.py",
        "core/change_order_agent.py",
        "core/communication_service.py",
        "core/workflow_engine.py",
        "core/resource_manager.py",
        "core/atom_meta_agent.py",
        "core/lifecycle_comm_generator.py",
        "core/background_agent_runner.py",
        "core/admin_bootstrap.py",
        "core/formula_memory.py",
        "core/uptime_tracker.py",
        "core/scheduler.py",
        "core/llm/byok_handler.py",
        "core/archive/database_v1.py",
        "integrations/chat_orchestrator.py",
        "integrations/universal_webhook_bridge.py",
        "integrations/zoho_workdrive_service.py",
    ]

    fixed_count = 0
    for rel_path in problematic_files:
        filepath = BACKEND_DIR / rel_path
        if not filepath.exists():
            continue

        print(f"🔧 {rel_path}")

        if fix_simple_pattern(filepath):
            print(f"  ✓ Fixed")
            fixed_count += 1
        else:
            print(f"  (no fix needed or failed)")
        print()

    print("=" * 70)
    print(f"Fixed {fixed_count} files")
    print("=" * 70)
    print()

    # Verify
    import ast
    print("Verifying fixes...")
    remaining = 0
    for rel_path in problematic_files:
        filepath = BACKEND_DIR / rel_path
        if not filepath.exists():
            continue

        try:
            with open(filepath, 'r') as f:
                content = f.read()
            ast.parse(content)
        except (SyntaxError, IndentationError) as e:
            print(f"  ✗ {rel_path}:{e.lineno} - {e.msg}")
            remaining += 1

    if remaining == 0:
        print("✅ All files fixed successfully!")
        return 0
    else:
        print(f"⚠️  {remaining} files still have errors")
        return 1


if __name__ == '__main__':
    sys.exit(scan_and_fix())
