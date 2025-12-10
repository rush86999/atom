#!/usr/bin/env python

import os
import re

def fix_file_syntax(file_path):
    """Fix syntax issues in Python files for compatibility"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        original_content = content

        # Fix response_model type annotations
        content = re.sub(r'response_model=Dict\[str, Any\]', '', content)
        content = re.sub(r'response_model=Dict\[str, Any\]', '', content)
        content = re.sub(r'-> Dict\[str, Any\]:', ':', content)

        # Fix function parameter type annotations
        content = re.sub(r'(\w+): (\w+)', r'\1', content)

        # Fix variable type annotations with defaults
        content = re.sub(r'(\w+): (\w+) = (.+)', r'\1 = \3', content)

        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            print("Fixed syntax in: {}".format(file_path))
            return True
        else:
            print("No changes needed for: {}".format(file_path))
            return False

    except Exception as e:
        print("Error fixing {}: {}".format(file_path, e))
        return False

def main():
    """Fix critical syntax issues in route files"""
    critical_files = [
        'integrations/zoom_oauth_routes.py',
        'integrations/social_store_routes.py',
        'integrations/asana_routes.py'
    ]

    print("Fixing critical syntax issues...")

    for file_path in critical_files:
        if os.path.exists(file_path):
            fix_file_syntax(file_path)
        else:
            print("File not found: {}".format(file_path))

    print("Syntax fixing completed.")

if __name__ == "__main__":
    main()