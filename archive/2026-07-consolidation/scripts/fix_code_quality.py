#!/usr/bin/env python3
"""
Code Quality Fixer Script for Atom

Automatically fixes common code quality issues:
- Black code formatting
- isort import sorting
- Removes trailing whitespace
- Fixes inconsistent line endings
- Normalizes blank lines

Usage:
    python scripts/fix_code_quality.py [--check] [--path PATH]

Options:
    --check       Only check for issues, don't fix them
    --path PATH   Path to check/fix (default: backend/)
    --verbose     Show detailed output

Examples:
    # Check for issues (read-only)
    python scripts/fix_code_quality.py --check

    # Fix all issues in backend/
    python scripts/fix_code_quality.py

    # Fix specific file
    python scripts/fix_code_quality.py --path backend/core/models.py

    # Fix with verbose output
    python scripts/fix_code_quality.py --verbose
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Tuple


def run_command(cmd: List[str], description: str, check_only: bool = False) -> Tuple[bool, str]:
    """Run a command and return success status and output."""
    print(f"\n{'Checking' if check_only else 'Running'}: {description}")
    print(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        if result.stdout:
            print(result.stdout)

        success = result.returncode == 0

        if not success and result.stderr:
            print(f"Error: {result.stderr}")

        return success, result.stdout
    except Exception as e:
        print(f"Failed to run command: {e}")
        return False, str(e)


def check_tools_installed() -> List[str]:
    """Check if required tools are installed."""
    missing = []

    required_tools = {
        'black': 'pip install black',
        'isort': 'pip install isort',
        'flake8': 'pip install flake8'
    }

    for tool, install_cmd in required_tools.items():
        try:
            subprocess.run(
                [tool, '--version'],
                capture_output=True,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(f"{tool} (install with: {install_cmd})")

    return missing


def format_with_black(path: str, check_only: bool = False) -> bool:
    """Format code with Black."""
    cmd = ['black', path]
    if check_only:
        cmd.append('--check')
    else:
        cmd.append('--quiet')

    success, output = run_command(
        cmd,
        "Black code formatter",
        check_only
    )

    return success


def sort_imports_with_isort(path: str, check_only: bool = False) -> bool:
    """Sort imports with isort."""
    cmd = ['isort', path]
    if check_only:
        cmd.append('--check-only')

    success, output = run_command(
        cmd,
        "isort import sorter",
        check_only
    )

    return success


def check_with_flake8(path: str) -> Tuple[bool, str]:
    """Check code with flake8."""
    cmd = [
        'flake8',
        path,
        '--max-line-length=120',
        '--extend-ignore=E203,W503,E302,E303,W293,W291',
        '--count',
        '--statistics'
    ]

    success, output = run_command(
        cmd,
        "flake8 linter",
        check_only=True
    )

    return success, output


def fix_line_endings(path: str) -> int:
    """Fix inconsistent line endings (CRLF -> LF)."""
    files_changed = 0

    for file_path in Path(path).rglob('*.py'):
        try:
            with open(file_path, 'rb') as f:
                content = f.read()

            # Check if file has CRLF line endings
            if b'\r\n' in content:
                # Convert to LF
                content = content.replace(b'\r\n', b'\n')

                with open(file_path, 'wb') as f:
                    f.write(content)

                files_changed += 1
                print(f"Fixed line endings: {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    return files_changed


def remove_trailing_whitespace(path: str) -> int:
    """Remove trailing whitespace from lines."""
    files_changed = 0

    for file_path in Path(path).rglob('*.py'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            new_lines = []
            changed = False

            for line in lines:
                # Remove trailing whitespace but preserve newline
                new_line = line.rstrip() + '\n' if line.endswith('\n') else line.rstrip()
                if new_line != line:
                    changed = True
                new_lines.append(new_line)

            if changed:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)

                files_changed += 1
                print(f"Removed trailing whitespace: {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    return files_changed


def fix_code_quality(
    path: str = 'backend/',
    check_only: bool = False,
    verbose: bool = False
) -> int:
    """Fix all code quality issues."""
    exit_code = 0

    print("=" * 80)
    print("ATOM CODE QUALITY FIXER")
    print("=" * 80)

    # Check if path exists
    if not Path(path).exists():
        print(f"Error: Path '{path}' does not exist")
        return 1

    # Check if tools are installed
    print("\nChecking for required tools...")
    missing = check_tools_installed()
    if missing:
        print("\n❌ Missing required tools:")
        for tool in missing:
            print(f"  - {tool}")
        print("\nPlease install missing tools and try again.")
        return 1

    print("✅ All required tools are installed")

    # Format with Black
    if not format_with_black(path, check_only):
        if check_only:
            print("\n⚠️  Black found formatting issues")
            exit_code = 1
        else:
            print("\n✅ Code formatted with Black")

    # Sort imports with isort
    if not sort_imports_with_isort(path, check_only):
        if check_only:
            print("\n⚠️  isort found import sorting issues")
            exit_code = 1
        else:
            print("\n✅ Imports sorted with isort")

    # Fix line endings (only if not check_only)
    if not check_only:
        files_changed = fix_line_endings(path)
        if files_changed > 0:
            print(f"\n✅ Fixed line endings in {files_changed} files")

    # Remove trailing whitespace (only if not check_only)
    if not check_only:
        files_changed = remove_trailing_whitespace(path)
        if files_changed > 0:
            print(f"\n✅ Removed trailing whitespace from {files_changed} files")

    # Check with flake8 (always run, even in check_only)
    print("\n" + "=" * 80)
    flake8_success, flake8_output = check_with_flake8(path)
    if flake8_success:
        print("✅ No flake8 errors found")
    else:
        print("⚠️  flake8 found issues (see above)")
        exit_code = 1

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if exit_code == 0:
        print("✅ All code quality checks passed!")
        if not check_only:
            print("   Code has been formatted and cleaned up")
    else:
        if check_only:
            print("⚠️  Code quality issues found")
            print("   Run without --check to fix automatically")
        else:
            print("⚠️  Some issues remain (see flake8 output above)")
            print("   Manual fixes may be required")

    print("=" * 80)

    return exit_code


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fix code quality issues in Atom codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--check',
        action='store_true',
        help='Only check for issues, don\'t fix them'
    )

    parser.add_argument(
        '--path',
        default='backend/',
        help='Path to check/fix (default: backend/)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )

    args = parser.parse_args()

    exit_code = fix_code_quality(
        path=args.path,
        check_only=args.check,
        verbose=args.verbose
    )

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
