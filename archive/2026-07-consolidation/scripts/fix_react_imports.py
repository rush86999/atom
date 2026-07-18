#!/usr/bin/env python3
"""
Automated React Import Fixer
Scans all .tsx files in pages directory and adds React import if missing
"""

import os
import re
from pathlib import Path

def has_jsx(content: str) -> bool:
    """Check if file contains JSX syntax"""
    jsx_patterns = [
        r'<\w+',  # Opening tags like <div
        r'</\w+>', # Closing tags like </div>
        r'<\w+\s+.*/>', # Self-closing tags
    ]
    return any(re.search(pattern, content) for pattern in jsx_patterns)

def has_react_import(content: str) -> bool:
    """Check if file already imports React"""
    # Check for various React import patterns
    patterns = [
        r'^import\s+React\s+from\s+["\']react["\']',
        r'^import\s+React,',
        r'^import\s+\{.*\}\s+from\s+["\']react["\'].*React', 
    ]
    return any(re.search(pattern, content, re.MULTILINE) for pattern in patterns)

def fix_react_import(file_path: Path) -> bool:
    """Add React import to file if needed"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Skip if no JSX or already has React import
        if not has_jsx(content):
            return False
        
        if has_react_import(content):
            return False
        
        # Find first import line
        lines = content.split('\n')
        first_import_idx = None
        
        for i, line in enumerate(lines):
            if line.strip().startswith('import '):
                first_import_idx = i
                break
        
        if first_import_idx is None:
            # No imports, add at top
            updated_content = f"import React from 'react';\n{content}"
        else:
            # Check if first import is from react (but not React itself)
            first_import = lines[first_import_idx]
            if "from 'react'" in first_import or 'from "react"' in first_import:
                # Modify the existing react import to include React
                if first_import.startswith('import {'):
                    # Change "import { useState } from 'react'" to "import React, { useState } from 'react'"
                    lines[first_import_idx] = first_import.replace('import {', 'import React, {')
                else:
                    # Edge case - just add React import before
                    lines.insert(first_import_idx, "import React from 'react';")
            else:
                # Add React import before first import
                lines.insert(first_import_idx, "import React from 'react';")
            
            updated_content = '\n'.join(lines)
        
        # Write updated content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"✓ Fixed: {file_path}")
        return True
        
    except Exception as e:
        print(f"✗ Error fixing {file_path}: {e}")
        return False

def main():
    pages_dir = Path('frontend-nextjs/pages')
    
    if not pages_dir.exists():
        print(f"Error: {pages_dir} not found")
        return
    
    # Find all .tsx files
    tsx_files = list(pages_dir.rglob('*.tsx'))
    print(f"Found {len(tsx_files)} .tsx files\n")
    
    fixed_count = 0
    skipped_count = 0
    
    for file_path in sorted(tsx_files):
        if fix_react_import(file_path):
            fixed_count += 1
        else:
            skipped_count += 1
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Fixed: {fixed_count} files")
    print(f"  Skipped: {skipped_count} files (already correct or no JSX)")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
