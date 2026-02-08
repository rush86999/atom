#!/usr/bin/env python3
"""
Auto-fix script for indentation errors in Atom backend.

This script fixes the common pattern where `with get_db_session() as db:`
is followed by an incorrectly indented `try:` block.

Also:
- Removes redundant `finally: db.close()` blocks (context manager handles cleanup)
- Adds proper exception handlers where missing
- Replaces bare `except:` with proper logging
"""

import ast
import os
from pathlib import Path
import re
import sys
from typing import List, Tuple

# Backend directory
BACKEND_DIR = Path("/Users/rushiparikh/projects/atom/backend")

# Patterns to fix
PATTERN_WITH_TRY = re.compile(
    r'(\s*)with get_db_session\(\) as db:\s*\n\s*try:',
    re.MULTILINE
)

PATTERN_FINALLY_CLOSE = re.compile(
    r'\s*finally:\s*\n\s*db\.close\(\)\s*\n',
    re.MULTILINE
)

PATTERN_BARE_EXCEPT = re.compile(
    r'except:\s*(?:pass|continue)\s*\n',
    re.MULTILINE
)

def fix_indentation_and_try_blocks(content: str, filepath: str) -> Tuple[str, int]:
    """
    Fix indentation issues with `with get_db_session()` followed by `try:`.
    Returns fixed content and number of fixes made.
    """
    original_content = content
    fixes = 0

    lines = content.split('\n')
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Pattern 1: `with get_db_session() as db:` followed by `try:` at same indentation
        if 'with get_db_session() as db:' in line:
            # Get the indentation of the with statement
            with_indent = len(line) - len(line.lstrip())
            new_lines.append(line)
            i += 1

            # Check if next line is `try:` with same or less indentation
            if i < len(lines):
                next_line = lines[i]
                try_indent = len(next_line) - len(next_line.lstrip()) if next_line.strip() else with_indent + 4

                # If `try:` is at same indentation or less than `with`, fix it
                if 'try:' in next_line and try_indent <= with_indent + 1:
                    # Add proper indentation (4 spaces more than with)
                    fixed_try = ' ' * (with_indent + 4) + 'try:'
                    new_lines.append(fixed_try)
                    fixes += 1
                    i += 1

                    # Continue processing subsequent lines with adjusted indentation
                    # until we exit the try block
                    base_indent = with_indent + 4
                    while i < len(lines):
                        current_line = lines[i]
                        if not current_line.strip():
                            new_lines.append(current_line)
                            i += 1
                            continue

                        current_indent = len(current_line) - len(current_line.lstrip())

                        # Check if we've exited the try/except/finally block
                        # (dedented back to or past the base with indentation)
                        if current_line.strip() and current_indent <= with_indent and not current_line.strip().startswith(('except', 'finally', 'except Exception', 'except ValueError', 'except TypeError', 'except json.JSONDecodeError')):
                            # We've exited the block, add the line as-is and break
                            new_lines.append(current_line)
                            i += 1
                            break

                        # Check for redundant `finally: db.close()`
                        if 'finally:' in current_line and 'db.close()' in lines[i+1] if i+1 < len(lines) else False:
                            # Skip the finally and db.close() lines
                            i += 2
                            # Continue to add remaining lines at original indentation
                            continue

                        new_lines.append(current_line)
                        i += 1
                    continue

        # Pattern 2: Replace bare `except: pass` or `except: continue`
        if 'except:' in line and ('pass' in line or 'continue' in line):
            # Extract indentation
            indent = len(line) - len(line.lstrip())
            indent_str = ' ' * indent

            # Get context for better error message
            context = filepath.name

            if 'continue' in line:
                # Common in loops - add debug log
                new_lines.append(indent_str + 'except Exception as e:')
                new_lines.append(indent_str + '    logger.debug(f"Operation failed in {context}: {{e}}")')
                new_lines.append(indent_str + '    continue')
                fixes += 1
            else:
                # Replace with proper logging
                new_lines.append(indent_str + 'except Exception as e:')
                new_lines.append(indent_str + f'    logger.warning(f"Operation failed in {context}: {{e}}")')
                fixes += 1
            i += 1
            continue

        # Pattern 3: Standalone bare `except:` followed by nothing
        if line.strip() == 'except:':
            indent = len(line) - len(line.lstrip())
            indent_str = ' ' * indent

            # Look ahead to see what's after
            if i + 1 < len(lines) and ('pass' in lines[i+1] or 'continue' in lines[i+1]):
                # Skip the except line, the next pattern handler will catch it
                new_lines.append(line)
            else:
                # Replace with proper exception handler
                new_lines.append(indent_str + 'except Exception as e:')
                new_lines.append(indent_str + f'    logger.warning(f"Unexpected error in {filepath.name}: {{e}}")')
                fixes += 1
            i += 1
            continue

        # Default: add line as-is
        new_lines.append(line)
        i += 1

    return '\n'.join(new_lines), fixes


def fix_file(filepath: Path) -> bool:
    """Fix a single file and return True if successful."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        fixed_content, fixes = fix_indentation_and_try_blocks(content, filepath)

        if fixes > 0:
            # Verify syntax is valid after fix
            try:
                ast.parse(fixed_content)
            except SyntaxError as e:
                print(f"  ⚠️  Syntax error after fix: {e}")
                return False

            # Write back
            with open(filepath, 'w') as f:
                f.write(fixed_content)

            print(f"  ✓ Fixed {fixes} issue(s)")
            return True
        else:
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

    # Find all Python files (excluding venv, __pycache__, etc.)
    python_files = []
    for root, dirs, files in os.walk(BACKEND_DIR):
        # Skip certain directories
        dirs[:] = [d for d in dirs if d not in [
            'venv', '__pycache__', 'node_modules', '.git',
            'dist', 'build', '.pytest_cache', 'scripts'
        ]]

        for file in files:
            if file.endswith('.py'):
                filepath = Path(root) / file
                python_files.append(filepath)

    print(f"Found {len(python_files)} Python files")
    print()

    # Check each file for syntax errors
    files_with_errors = []
    for filepath in python_files:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            ast.parse(content)
        except (SyntaxError, IndentationError) as e:
            files_with_errors.append((filepath, e))

    if not files_with_errors:
        print("✅ No syntax errors found!")
        return 0

    print(f"Found {len(files_with_errors)} files with syntax errors:")
    print()

    fixed_count = 0
    for filepath, error in files_with_errors:
        print(f"🔧 {filepath.relative_to(BACKEND_DIR)}:{error.lineno}")
        print(f"   {error.msg}")

        # Attempt to fix
        if fix_file(filepath):
            fixed_count += 1
        print()

    print("=" * 70)
    print(f"Fixed {fixed_count} / {len(files_with_errors)} files")
    print("=" * 70)
    print()

    # Verify all fixes
    print("Verifying fixes...")
    remaining_errors = []
    for filepath, _ in files_with_errors:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            ast.parse(content)
        except (SyntaxError, IndentationError) as e:
            remaining_errors.append((filepath, e))

    if remaining_errors:
        print(f"⚠️  {len(remaining_errors)} files still have errors:")
        for filepath, error in remaining_errors:
            print(f"   {filepath.relative_to(BACKEND_DIR)}:{error.lineno} - {error.msg}")
        return 1
    else:
        print("✅ All files fixed successfully!")
        return 0


if __name__ == '__main__':
    sys.exit(scan_and_fix())
