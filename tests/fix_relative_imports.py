#!/usr/bin/env python3
"""
Script to fix relative imports in the Atom backend Python API service.
This script converts relative imports (from . import module) to absolute imports (import module)
in all Python files in the backend/python-api-service directory.
"""

import os
import re
import glob
from pathlib import Path

def fix_relative_imports(file_path):
    """Fix relative imports in a Python file"""
    with open(file_path, 'r') as f:
        content = f.read()

    # Pattern to match relative imports
    patterns = [
        r'from \. import (\w+)',
        r'from \.(\w+) import (\w+)',
        r'from \.\. import (\w+)',
        r'from \.\.(\w+) import (\w+)'
    ]

    original_content = content
    changes_made = False

    # Fix from . import module
    content = re.sub(r'from \. import (\w+)', r'import \1', content)

    # Fix from .module import function
    content = re.sub(r'from \.(\w+) import (\w+)', r'from \1 import \2', content)

    # Fix from .. import module
    content = re.sub(r'from \.\. import (\w+)', r'import \1', content)

    # Fix from ..module import function
    content = re.sub(r'from \.\.(\w+) import (\w+)', r'from \1 import \2', content)

    if content != original_content:
        changes_made = True
        with open(file_path, 'w') as f:
            f.write(content)

    return changes_made

def main():
    """Main function to fix imports in all Python files"""
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend', 'python-api-service')

    if not os.path.exists(backend_dir):
        print(f"Error: Backend directory not found: {backend_dir}")
        return

    # Get all Python files
    python_files = glob.glob(os.path.join(backend_dir, '*.py'))

    print(f"Found {len(python_files)} Python files in {backend_dir}")

    changed_files = []
    for file_path in python_files:
        filename = os.path.basename(file_path)
        if filename == 'fix_relative_imports.py':
            continue  # Skip this script

        try:
            changed = fix_relative_imports(file_path)
            if changed:
                changed_files.append(filename)
                print(f"✅ Fixed imports in: {filename}")
            else:
                print(f"✓ No changes needed: {filename}")
        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")

    print(f"\nSummary:")
    print(f"Total files processed: {len(python_files)}")
    print(f"Files changed: {len(changed_files)}")

    if changed_files:
        print("\nChanged files:")
        for filename in changed_files:
            print(f"  - {filename}")

if __name__ == '__main__':
    main()
