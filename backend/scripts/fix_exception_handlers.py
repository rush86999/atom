#!/usr/bin/env python3
"""
Script to fix bare exception handlers in the codebase.

This script identifies and fixes bare except: clauses by:
1. Adding logging with appropriate levels
2. Re-raising exceptions for critical operations
3. Handling expected exceptions specifically
"""

import os
import re
import sys
from pathlib import Path

def get_indentation(line):
    """Get leading whitespace from a line"""
    return line[:len(line) - len(line.lstrip())]

def fix_exception_handler(content, file_path):
    """Fix bare exception handlers in file content"""
    lines = content.split('\n')
    fixed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Look for bare except:
        if re.match(r'^\s*except:\s*$', line):
            indent = get_indentation(line)

            # Look at what follows to determine the fix
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or lines[j].startswith(indent + ' ')):
                j += 1

            following_lines = lines[i+1:j]

            # Check if it's a pass statement
            if any('pass' in ln.strip() for ln in following_lines):
                # Replace with logging
                fixed_lines.append(indent + "except Exception as e:")
                fixed_lines.append(indent + f"    logger.debug(f\"[{{file_path.name}}] Non-critical error: {{e}}\")")
                i += 1
                continue

            # Check if it's logging already
            if any('logger' in ln or 'print' in ln for ln in following_lines):
                # Just add Exception as e
                fixed_lines.append(indent + "except Exception as e:")
                i += 1
                continue

            # Check if it's cleanup code
            if any('clean' in ln.lower() or 'close' in ln.lower() for ln in following_lines):
                fixed_lines.append(indent + "except Exception as e:")
                fixed_lines.append(indent + f"    logger.debug(f\"[{{file_path.name}}] Cleanup error (non-critical): {{e}}\")")
                i += 1
                continue

            # Default: Add logging and re-raise for critical operations
            fixed_lines.append(indent + "except Exception as e:")
            fixed_lines.append(indent + f"    logger.error(f\"[{{file_path.name}}] Error: {{e}}\", exc_info=True)")
            fixed_lines.append(indent + "    raise")
            i += 1
            continue

        fixed_lines.append(line)
        i += 1

    return '\n'.join(fixed_lines)

def main():
    backend_dir = Path("backend")
    files_fixed = 0

    print("Fixing bare exception handlers...")
    print()

    for py_file in backend_dir.rglob("*.py"):
        # Skip test files
        if 'test' in py_file.name or 'venv' in str(py_file):
            continue

        try:
            with open(py_file, 'r') as f:
                content = f.read()

            # Check if file has bare except:
            if 'except:' not in content:
                continue

            # Fix it
            fixed_content = fix_exception_handler(content, py_file)

            if fixed_content != content:
                with open(py_file, 'w') as f:
                    f.write(fixed_content)
                print(f"✅ Fixed: {py_file}")
                files_fixed += 1

        except Exception as e:
            print(f"❌ Error processing {py_file}: {e}")

    print()
    print(f"Fixed {files_fixed} files")

if __name__ == "__main__":
    sys.exit(main())
